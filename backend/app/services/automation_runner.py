from datetime import datetime, timezone, timedelta
import re
import uuid
from typing import Optional, Dict, Any, Tuple
from zoneinfo import ZoneInfo
from cryptography.fernet import InvalidToken
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.entities import (
    FacebookPage, Post, Comment, CommentStatus,
    RestrictedKeyword, AutomationRule, ActionLog, ActionStatus,
    PostContentVersion, ContentGenerationRun,
)
from app.services.gemini_service import GeminiServiceError, gemini_service
from app.services.meta_client import MetaAPIError, meta_client

class AutomationEngine:
    async def is_within_operating_hours(
        self,
        page: FacebookPage,
        now: Optional[datetime] = None,
    ) -> bool:
        """Check if current time is within page's allowed operating hours."""
        if not page.operating_hours_start or not page.operating_hours_end:
            return True
        timezone_info = ZoneInfo(page.timezone or "Asia/Kathmandu")
        local_now = (now or datetime.now(timezone.utc)).astimezone(timezone_info)
        current_time = local_now.time().replace(tzinfo=None)
        start_time = datetime.strptime(page.operating_hours_start, "%H:%M").time()
        end_time = datetime.strptime(page.operating_hours_end, "%H:%M").time()
        if start_time <= end_time:
            return start_time <= current_time <= end_time
        return current_time >= start_time or current_time <= end_time

    async def check_rate_limit(self, db: AsyncSession, page_id: int, max_per_hour: int) -> bool:
        """Check if page has exceeded its actions-per-hour rate limit."""
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        query = select(func.count(ActionLog.id)).where(
            ActionLog.page_id == page_id,
            ActionLog.action_type.in_(["comment_reply", "comment_like"]),
            ActionLog.status == ActionStatus.SUCCESS,
            ActionLog.created_at >= one_hour_ago
        )
        result = await db.execute(query)
        count = result.scalar() or 0
        return count < max_per_hour

    async def check_restricted_keywords(self, db: AsyncSession, text: str) -> Tuple[bool, Optional[str]]:
        """Check if comment contains any blacklisted or sensitive keywords."""
        result = await db.execute(select(RestrictedKeyword))
        keywords = result.scalars().all()
        text_lower = text.lower()
        for kw in keywords:
            if kw.keyword.lower() in text_lower:
                return True, f"Contains restricted keyword: '{kw.keyword}' ({kw.category})"
        return False, None

    async def find_matching_template_rule(
        self,
        db: AsyncSession,
        page_id: int,
        text: str,
    ) -> Optional[AutomationRule]:
        result = await db.execute(
            select(AutomationRule)
            .where(
                AutomationRule.is_active.is_(True),
                or_(AutomationRule.page_id.is_(None), AutomationRule.page_id == page_id),
            )
            .order_by(AutomationRule.id)
        )
        rules = result.scalars().all()
        text_lower = text.casefold()
        matching = [
            rule
            for rule in rules
            if rule.rule_type in {"keyword_auto_reply", "template"}
            and rule.trigger_keyword
            and rule.response_template
            and rule.response_template.strip()
            and rule.trigger_keyword.casefold() in text_lower
        ]
        matching.sort(key=lambda rule: (rule.page_id != page_id, rule.id))
        return matching[0] if matching else None

    async def process_incoming_comment(
        self,
        db: AsyncSession,
        page: FacebookPage,
        post: Post,
        sender_name: str,
        sender_id: str,
        message: str,
        meta_comment_id: str,
        is_simulated: bool = False,
    ) -> Comment:
        """Core automation pipeline for an incoming comment."""
        # 1. Deduplication check
        existing = await db.execute(select(Comment).where(Comment.meta_comment_id == meta_comment_id))
        if existing.scalar_one_or_none():
            return None

        # 2. Check restricted keywords
        has_restricted, reason = await self.check_restricted_keywords(db, message)

        # 3. Apply an explicit matching template, otherwise generate an AI draft.
        generation_error = None
        matching_rule = await self.find_matching_template_rule(db, page.id, message)
        if matching_rule:
            ai_result = {
                "detected_language": (
                    matching_rule.target_language
                    if matching_rule.target_language in {"en", "ne"}
                    else "ne" if re.search(r"[\u0900-\u097f]", message) else "en"
                ),
                "sentiment": "negative" if has_restricted else "neutral",
                "reply": (
                    matching_rule.response_template
                    .replace("{name}", sender_name)
                    .replace("{comment}", message)
                ).strip(),
                "source": "automation_rule",
            }
        else:
            try:
                ai_result = await gemini_service.generate_comment_reply(
                    comment_text=message,
                    post_context=post.message or "",
                    brand_context=page.brand_context or "",
                    tone=page.response_tone or "friendly",
                    target_language=page.default_language if page.default_language != "bilingual" else None
                )
            except GeminiServiceError as exc:
                ai_result = {}
                generation_error = str(exc)
        if ai_result.get("fallback_reason"):
            generation_error = ai_result["fallback_reason"]

        detected_lang = ai_result.get("detected_language", "en")
        sentiment = ai_result.get("sentiment", "neutral")
        ai_draft = ai_result.get("reply", "")

        # 4. Determine approval vs auto-publish
        can_auto_publish = (
            not settings.SIMULATION_MODE and
            page.automation_enabled and
            page.auto_approve_enabled and
            not is_simulated and
            ai_result.get("source") == "gemini_api" and
            sentiment != "negative" and
            ai_result.get("confidence", 0) >= 0.8 and
            not has_restricted and
            await self.is_within_operating_hours(page) and
            await self.check_rate_limit(db, page.id, page.max_actions_per_hour)
        )

        status = CommentStatus.PUBLISHED if can_auto_publish else CommentStatus.PENDING_APPROVAL
        final_reply = ai_draft if can_auto_publish else None
        published_at = datetime.now(timezone.utc) if can_auto_publish else None
        is_liked = False

        # Create Comment entity
        comment = Comment(
            meta_comment_id=meta_comment_id,
            post_id=post.id,
            page_id=page.id,
            sender_id=sender_id,
            sender_name=sender_name,
            message=message,
            detected_language=detected_lang,
            sentiment=sentiment,
            ai_draft_reply=ai_draft or None,
            ai_generation_source=ai_result.get("source"),
            is_simulated=is_simulated,
            final_reply=final_reply,
            status=status,
            published_at=published_at,
            error_message="; ".join(
                item for item in (reason, generation_error) if item
            ) or None
        )
        db.add(comment)
        await db.flush()

        # 5. If auto-publish eligible, execute Meta Graph API post
        if can_auto_publish:
            try:
                access_token = meta_client.get_page_access_token(page)
                # Post reply
                await meta_client.publish_comment_reply(meta_comment_id, ai_draft, access_token)
                
                # Optional policy-compliant like
                if page.auto_like_enabled:
                    await meta_client.like_comment(meta_comment_id, access_token)
                    comment.is_liked = True
                    page.total_likes_given += 1

                page.total_comments_replied += 1
                
                # Log success
                log = ActionLog(
                    page_id=page.id,
                    action_type="comment_reply",
                    status=ActionStatus.SUCCESS,
                    details={
                        "comment_id": meta_comment_id,
                        "reply": ai_draft,
                        "mode": "full_auto",
                        "language": detected_lang,
                        "generation_source": ai_result.get("source"),
                        "confidence": ai_result.get("confidence"),
                    }
                )
                db.add(log)
            except (MetaAPIError, InvalidToken) as e:
                comment.status = CommentStatus.FAILED
                comment.error_message = str(e)
                log = ActionLog(
                    page_id=page.id,
                    action_type="comment_reply",
                    status=ActionStatus.FAILED,
                    error_message=str(e),
                    details={"comment_id": meta_comment_id}
                )
                db.add(log)
        else:
            # Queued for operator approval
            log = ActionLog(
                page_id=page.id,
                action_type="comment_queued",
                status=ActionStatus.PENDING,
                details={
                    "comment_id": meta_comment_id,
                    "draft": ai_draft,
                    "generation_source": ai_result.get("source"),
                    "simulated": is_simulated,
                    "flagged": has_restricted,
                    "reason": reason or generation_error
                }
            )
            db.add(log)

        await db.commit()
        await db.refresh(comment)
        return comment

    async def approve_and_publish_comment(
        self,
        db: AsyncSession,
        comment: Comment,
        edited_reply: Optional[str] = None,
        also_like: bool = True
    ) -> bool:
        """Operator explicitly approves or edits and publishes a comment."""
        page = comment.page
        reply_to_post = edited_reply or comment.ai_draft_reply
        if comment.is_simulated or not reply_to_post or not reply_to_post.strip():
            return False

        try:
            access_token = meta_client.get_page_access_token(page)
            # Publish reply to Meta
            await meta_client.publish_comment_reply(comment.meta_comment_id, reply_to_post, access_token)
            
            if also_like and not comment.is_liked:
                await meta_client.like_comment(comment.meta_comment_id, access_token)
                comment.is_liked = True
                page.total_likes_given += 1

            comment.status = CommentStatus.PUBLISHED
            comment.final_reply = reply_to_post
            comment.published_at = datetime.now(timezone.utc)
            comment.error_message = None
            page.total_comments_replied += 1

            log = ActionLog(
                page_id=page.id,
                action_type="comment_reply_approved",
                status=ActionStatus.SUCCESS,
                details={
                    "comment_id": comment.meta_comment_id,
                    "reply": reply_to_post,
                    "operator_edited": bool(edited_reply)
                }
            )
            db.add(log)
            await db.commit()
            return True
        except (MetaAPIError, InvalidToken) as e:
            comment.status = CommentStatus.FAILED
            comment.error_message = str(e)
            log = ActionLog(
                page_id=page.id,
                action_type="comment_reply_approved",
                status=ActionStatus.FAILED,
                error_message=str(e)
            )
            db.add(log)
            await db.commit()
            return False

    async def generate_daily_post(
        self,
        db: AsyncSession,
        page: FacebookPage,
        topic: Optional[str] = None,
        language: str = "ne",
        tone: str = "promotional",
        auto_publish: bool = False,
        allow_auto_publish: bool = False,
        scheduled_for: Optional[datetime] = None,
        category: Optional[str] = None,
        brand_context: Optional[str] = None,
        recent_messages: Optional[list[str]] = None,
        existing_post: Optional[Post] = None,
        actor_user_id: Optional[int] = None,
        generation_run: Optional[ContentGenerationRun] = None,
    ) -> Post:
        """Generate a Facebook draft. Content generation never publishes to Meta."""
        ai_post = await gemini_service.generate_social_post(
            brand_context=brand_context or page.brand_context or "",
            topic=topic or page.post_topics_prompt or "Special product deals and customer benefits",
            language=language or page.default_language or "ne",
            tone=tone or page.response_tone or "professional and engaging",
            category=category,
            recent_posts=recent_messages,
        )

        message = ai_post.get("message")
        if not isinstance(message, str) or not message.strip() or len(message) > 63206:
            raise GeminiServiceError("Gemini returned content that did not pass draft validation")

        if existing_post is not None:
            if existing_post.status != "draft":
                raise ValueError("Only draft posts can be regenerated")
            existing_post.message = message.strip()
            existing_post.media_url = ai_post.get("media_url")
            existing_post.generation_source = ai_post.get("source")
            existing_post.topic = topic or existing_post.topic
            existing_post.content_category = category or existing_post.content_category
            existing_post.content_language = language
            post = existing_post
            event_type = "regenerated"
        else:
            post = Post(
                meta_post_id=f"{page.meta_page_id}_draft_{uuid.uuid4().hex}",
                page_id=page.id,
                message=message.strip(),
                media_url=ai_post.get("media_url"),
                is_monitored=True,
                is_ai_generated=True,
                generation_source=ai_post.get("source"),
                status="draft",
                topic=topic,
                content_category=category,
                content_language=language,
            )
            db.add(post)
            event_type = "generated"
        db.add(
            ActionLog(
                page_id=page.id,
                action_type="post_draft_generated",
                status=ActionStatus.SUCCESS,
                details={
                    "generation_source": ai_post.get("source"),
                    "status": "draft",
                    "category": category,
                    "language": language,
                },
            )
        )
        await db.flush()
        version_result = await db.execute(
            select(func.max(PostContentVersion.version)).where(
                PostContentVersion.post_id == post.id
            )
        )
        next_version = (version_result.scalar() or 0) + 1
        db.add(
            PostContentVersion(
                post_id=post.id,
                version=next_version,
                event_type=event_type,
                message=message.strip(),
                actor_user_id=actor_user_id,
            )
        )
        if generation_run is not None:
            generation_run.post_id = post.id
            generation_run.status = "completed"
            generation_run.completed_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(post)
        return post

    async def publish_draft_post(
        self,
        db: AsyncSession,
        post: Post,
        edited_message: Optional[str] = None,
        media_url: Optional[str] = None
    ) -> bool:
        """Publish a pre-generated draft post to Facebook."""
        page = post.page
        message_to_post = edited_message or post.message
        img_to_post = media_url or post.media_url
        if post.status not in {"approved", "scheduled"} or not message_to_post or not message_to_post.strip():
            return False

        try:
            access_token = meta_client.get_page_access_token(page)
            res = await meta_client.create_page_post(
                page_id=page.meta_page_id,
                message=message_to_post,
                access_token=access_token,
                media_url=img_to_post
            )
            if res.get("verified") is not True:
                raise MetaAPIError(
                    "Meta did not verify the Page post; it was not marked as published",
                    published_post_id=res.get("id"),
                    publication_uncertain=True,
                )
            post.meta_post_id = res.get("id", post.meta_post_id)
            post.permalink_url = res.get("permalink_url", post.permalink_url)
            post.status = "published"
            post.message = message_to_post
            post.media_url = img_to_post
            post.published_at = datetime.now(timezone.utc)
            page.posts_created_today = (page.posts_created_today or 0) + 1

            log = ActionLog(
                page_id=page.id,
                action_type="draft_post_published",
                status=ActionStatus.SUCCESS,
                details={"post_id": post.meta_post_id, "edited": bool(edited_message)}
            )
            db.add(log)
            await db.commit()
            return True
        except (MetaAPIError, InvalidToken) as e:
            is_uncertain = isinstance(e, MetaAPIError) and e.publication_uncertain
            post.status = "pending_verification" if is_uncertain else "failed"
            meta_error = e.meta_error if isinstance(e, MetaAPIError) else None
            log = ActionLog(
                page_id=page.id,
                action_type="draft_post_published",
                status=ActionStatus.PENDING if is_uncertain else ActionStatus.FAILED,
                error_message=str(e),
                details={
                    "post_id": getattr(e, "published_post_id", None),
                    "verification_required": is_uncertain,
                    "http_status": getattr(e, "http_status", None),
                    "meta_response_error": meta_error,
                },
            )
            db.add(log)
            await db.commit()
            return False

automation_engine = AutomationEngine()
