from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import (
    FacebookPage, Post, Comment, CommentStatus,
    RestrictedKeyword, ActionLog, ActionStatus
)
from app.services.gemini_service import gemini_service
from app.services.meta_client import meta_client
from app.core.security import decrypt_token

class AutomationEngine:
    async def is_within_operating_hours(self, page: FacebookPage) -> bool:
        """Check if current time is within page's allowed operating hours."""
        if not page.operating_hours_start or not page.operating_hours_end:
            return True
        now_time = datetime.now().strftime("%H:%M")
        return page.operating_hours_start <= now_time <= page.operating_hours_end

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

    async def process_incoming_comment(
        self,
        db: AsyncSession,
        page: FacebookPage,
        post: Post,
        sender_name: str,
        sender_id: str,
        message: str,
        meta_comment_id: str
    ) -> Comment:
        """Core automation pipeline for an incoming comment."""
        # 1. Deduplication check
        existing = await db.execute(select(Comment).where(Comment.meta_comment_id == meta_comment_id))
        if existing.scalar_one_or_none():
            return None

        # 2. Check restricted keywords
        has_restricted, reason = await self.check_restricted_keywords(db, message)

        # 3. Generate AI bilingual draft
        ai_result = await gemini_service.generate_comment_reply(
            comment_text=message,
            post_context=post.message or "",
            brand_context=page.brand_context or "",
            tone=page.response_tone or "friendly",
            target_language=page.default_language if page.default_language != "bilingual" else None
        )

        detected_lang = ai_result.get("detected_language", "en")
        sentiment = ai_result.get("sentiment", "neutral")
        ai_draft = ai_result.get("reply", "")

        # 4. Determine approval vs auto-publish
        can_auto_publish = (
            page.automation_enabled and
            page.auto_approve_enabled and
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
            ai_draft_reply=ai_draft,
            final_reply=final_reply,
            status=status,
            published_at=published_at,
            error_message=reason if has_restricted else None
        )
        db.add(comment)
        await db.flush()

        # 5. If auto-publish eligible, execute Meta Graph API post
        if can_auto_publish:
            access_token = decrypt_token(page.access_token_enc) if page.access_token_enc else ""
            try:
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
                        "language": detected_lang
                    }
                )
                db.add(log)
            except Exception as e:
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
                    "flagged": has_restricted,
                    "reason": reason
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
        access_token = decrypt_token(page.access_token_enc) if page.access_token_enc else ""

        try:
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
        except Exception as e:
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

automation_engine = AutomationEngine()
