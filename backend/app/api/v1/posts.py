from datetime import datetime, timezone
import uuid
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.database import get_db
from app.models.entities import (
    ActionLog,
    ActionStatus,
    ContentGenerationConfig,
    ContentGenerationRun,
    FacebookPage,
    Post,
    PostContentVersion,
    User,
    UserRole,
)
from app.schemas.schemas import (
    ContentAutomationConfigRead,
    ContentAutomationConfigUpdate,
    ContentGenerationRunRead,
    PostRead,
    PostDraftGenerateRequest,
    PostDraftUpdate,
    PostContentVersionRead,
    PostRejectRequest,
    PostScheduleRequest,
    PostPublishRequest,
)
from app.services.automation_runner import automation_engine
from app.services.gemini_service import GeminiServiceError
from app.api.v1.auth import get_current_user, require_roles

router = APIRouter(
    prefix="/posts",
    tags=["Posts Monitor & Daily Creator"],
    dependencies=[Depends(get_current_user)],
)
CONTENT_EDITOR_ROLES = (
    UserRole.SUPER_ADMIN,
    UserRole.COMPANY_ADMIN,
    UserRole.ADMIN,
    UserRole.OPERATOR,
)

@router.get("/", response_model=List[PostRead])
async def list_posts(
    page_id: Optional[int] = Query(None, description="Filter by Facebook Page ID"),
    status: Optional[str] = Query(None, description="Filter by status: published, draft, failed"),
    db: AsyncSession = Depends(get_db)
):
    query = select(Post).order_by(Post.created_at.desc())
    if page_id:
        query = query.where(Post.page_id == page_id)
    if status:
        query = query.where(Post.status == status)
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/drafts", response_model=List[PostRead])
async def list_draft_posts(
    page_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve all AI-generated post drafts waiting for review."""
    query = select(Post).where(Post.status == "draft").order_by(Post.created_at.desc())
    if page_id:
        query = query.where(Post.page_id == page_id)
    result = await db.execute(query)
    return result.scalars().all()


async def _get_content_config(
    db: AsyncSession,
    page_id: int,
) -> ContentGenerationConfig:
    page_result = await db.execute(select(FacebookPage).where(FacebookPage.id == page_id))
    if not page_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Page not found")
    result = await db.execute(
        select(ContentGenerationConfig).where(ContentGenerationConfig.page_id == page_id)
    )
    config = result.scalar_one_or_none()
    if config is None:
        config = ContentGenerationConfig(page_id=page_id)
        db.add(config)
        await db.commit()
        await db.refresh(config)
    return config


@router.get(
    "/automation-config",
    response_model=ContentAutomationConfigRead,
    dependencies=[Depends(require_roles(*CONTENT_EDITOR_ROLES))],
)
async def get_content_automation_config(
    page_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
):
    return await _get_content_config(db, page_id)


@router.put(
    "/automation-config",
    response_model=ContentAutomationConfigRead,
    dependencies=[Depends(require_roles(*CONTENT_EDITOR_ROLES))],
)
async def update_content_automation_config(
    update: ContentAutomationConfigUpdate,
    page_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
):
    config = await _get_content_config(db, page_id)
    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(config, field, value)
    config.approval_required = True
    config.auto_publish_enabled = False
    await db.commit()
    await db.refresh(config)
    return config


@router.post(
    "/generate-draft",
    response_model=PostRead,
    dependencies=[Depends(require_roles(*CONTENT_EDITOR_ROLES))],
)
async def generate_post_draft(
    draft_req: PostDraftGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate and persist a draft; this endpoint never publishes content."""
    res_page = await db.execute(select(FacebookPage).where(FacebookPage.id == draft_req.page_id))
    page = res_page.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    config = await _get_content_config(db, page.id)
    run_key = f"manual:{draft_req.request_id or uuid.uuid4().hex}"
    existing_run_result = await db.execute(
        select(ContentGenerationRun).where(
            ContentGenerationRun.page_id == page.id,
            ContentGenerationRun.run_key == run_key,
        )
    )
    existing_run = existing_run_result.scalar_one_or_none()
    if existing_run:
        if existing_run.status == "completed" and existing_run.post_id:
            post_result = await db.execute(
                select(Post).where(Post.id == existing_run.post_id)
            )
            post = post_result.scalar_one_or_none()
            if post:
                return post
        raise HTTPException(
            status_code=409,
            detail="This generation request is already in progress or has failed. Start a new request.",
        )

    recent_result = await db.execute(
        select(Post.message)
        .where(
            Post.page_id == page.id,
            Post.is_ai_generated.is_(True),
            Post.message.is_not(None),
        )
        .order_by(Post.created_at.desc())
        .limit(10)
    )
    recent_messages = [message for message in recent_result.scalars().all() if message]
    category = draft_req.category
    if not category:
        categories = config.categories or ["Company promotions"]
        generated_count_result = await db.execute(
            select(func.count(Post.id)).where(
                Post.page_id == page.id,
                Post.is_ai_generated.is_(True),
            )
        )
        category = categories[generated_count_result.scalar() % len(categories)]
    topic = draft_req.topic or category
    language = draft_req.language or (config.languages or ["en", "ne"])[0]
    brand_context = "\n".join(
        item for item in (config.brand_context, page.brand_context) if item
    )
    run = ContentGenerationRun(
        page_id=page.id,
        run_key=run_key,
        source="manual",
        status="in_progress",
        topic=topic,
        content_category=category,
    )
    db.add(run)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        duplicate_result = await db.execute(
            select(ContentGenerationRun).where(
                ContentGenerationRun.page_id == page.id,
                ContentGenerationRun.run_key == run_key,
            )
        )
        duplicate_run = duplicate_result.scalar_one_or_none()
        if duplicate_run and duplicate_run.status == "completed" and duplicate_run.post_id:
            post_result = await db.execute(
                select(Post).where(Post.id == duplicate_run.post_id)
            )
            duplicate_post = post_result.scalar_one_or_none()
            if duplicate_post:
                return duplicate_post
        raise HTTPException(
            status_code=409,
            detail="This generation request is already in progress.",
        )
    await db.refresh(run)
    try:
        post = await automation_engine.generate_daily_post(
            db=db,
            page=page,
            topic=topic,
            language=language,
            tone=draft_req.tone or config.tone,
            allow_auto_publish=False,
            category=category,
            brand_context=brand_context,
            recent_messages=recent_messages,
            actor_user_id=current_user.id,
            generation_run=run,
        )
    except GeminiServiceError as exc:
        run.status = "failed"
        run.error_message = str(exc)
        run.completed_at = datetime.now(timezone.utc)
        db.add(
            ActionLog(
                page_id=page.id,
                action_type="post_draft_generation",
                status=ActionStatus.FAILED,
                error_message=str(exc),
            )
        )
        await db.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return post


@router.post(
    "/{post_id}/regenerate",
    response_model=PostRead,
    dependencies=[Depends(require_roles(*CONTENT_EDITOR_ROLES))],
)
async def regenerate_post_draft(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Post).options(selectinload(Post.page)).where(Post.id == post_id)
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.status != "draft":
        raise HTTPException(status_code=409, detail="Only draft posts can be regenerated")
    config = await _get_content_config(db, post.page_id)
    recent_result = await db.execute(
        select(Post.message)
        .where(
            Post.page_id == post.page_id,
            Post.id != post.id,
            Post.is_ai_generated.is_(True),
            Post.message.is_not(None),
        )
        .order_by(Post.created_at.desc())
        .limit(10)
    )
    recent_messages = [message for message in recent_result.scalars().all() if message]
    run = ContentGenerationRun(
        page_id=post.page_id,
        run_key=f"regenerate:{post.id}:{uuid.uuid4().hex}",
        source="regenerate",
        status="in_progress",
        topic=post.topic,
        content_category=post.content_category,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    try:
        return await automation_engine.generate_daily_post(
            db=db,
            page=post.page,
            topic=post.topic,
            language=post.content_language or "en",
            tone=config.tone,
            category=post.content_category,
            brand_context="\n".join(
                item for item in (config.brand_context, post.page.brand_context) if item
            ),
            recent_messages=recent_messages,
            existing_post=post,
            actor_user_id=current_user.id,
            generation_run=run,
        )
    except GeminiServiceError as exc:
        run.status = "failed"
        run.error_message = str(exc)
        run.completed_at = datetime.now(timezone.utc)
        db.add(
            ActionLog(
                page_id=post.page_id,
                action_type="post_draft_regeneration",
                status=ActionStatus.FAILED,
                error_message=str(exc),
                details={"post_id": post.id},
            )
        )
        await db.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.put(
    "/{post_id}/draft",
    response_model=PostRead,
    dependencies=[Depends(require_roles(*CONTENT_EDITOR_ROLES))],
)
async def update_post_draft(
    post_id: int,
    draft_update: PostDraftUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Edit a generated draft without publishing it."""
    res = await db.execute(select(Post).where(Post.id == post_id))
    post = res.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.status != "draft":
        raise HTTPException(status_code=409, detail="Only draft posts can be edited")

    post.message = draft_update.message
    if "media_url" in draft_update.model_fields_set:
        post.media_url = draft_update.media_url
    db.add(
        ActionLog(
            page_id=post.page_id,
            action_type="post_draft_edited",
            status=ActionStatus.SUCCESS,
            details={"post_id": post.id, "media_updated": "media_url" in draft_update.model_fields_set},
        )
    )
    version_result = await db.execute(
        select(func.max(PostContentVersion.version)).where(
            PostContentVersion.post_id == post.id
        )
    )
    db.add(
        PostContentVersion(
            post_id=post.id,
            version=(version_result.scalar() or 0) + 1,
            event_type="edited",
            message=post.message,
            actor_user_id=current_user.id,
        )
    )
    await db.commit()
    await db.refresh(post)
    return post


@router.post(
    "/{post_id}/approve",
    response_model=PostRead,
    dependencies=[Depends(require_roles(*CONTENT_EDITOR_ROLES))],
)
async def approve_post_draft(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Post).where(Post.id == post_id))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.status != "draft":
        raise HTTPException(status_code=409, detail="Only draft posts can be approved")
    post.status = "approved"
    post.approved_at = datetime.now(timezone.utc)
    post.approved_by_user_id = current_user.id
    db.add(
        ActionLog(
            page_id=post.page_id,
            action_type="post_draft_approved",
            status=ActionStatus.SUCCESS,
            details={"post_id": post.id},
        )
    )
    version_result = await db.execute(
        select(func.max(PostContentVersion.version)).where(
            PostContentVersion.post_id == post.id
        )
    )
    db.add(
        PostContentVersion(
            post_id=post.id,
            version=(version_result.scalar() or 0) + 1,
            event_type="approved",
            message=post.message or "",
            actor_user_id=current_user.id,
        )
    )
    await db.commit()
    await db.refresh(post)
    return post


@router.post(
    "/{post_id}/reject",
    response_model=PostRead,
    dependencies=[Depends(require_roles(*CONTENT_EDITOR_ROLES))],
)
async def reject_post_draft(
    post_id: int,
    request: PostRejectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Post).where(Post.id == post_id))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.status not in {"draft", "approved", "scheduled"}:
        raise HTTPException(status_code=409, detail="This post can no longer be rejected")
    post.status = "rejected"
    post.scheduled_for = None
    post.rejection_reason = request.reason
    db.add(
        ActionLog(
            page_id=post.page_id,
            action_type="post_draft_rejected",
            status=ActionStatus.SUCCESS,
            details={"post_id": post.id, "reason": request.reason},
        )
    )
    version_result = await db.execute(
        select(func.max(PostContentVersion.version)).where(
            PostContentVersion.post_id == post.id
        )
    )
    db.add(
        PostContentVersion(
            post_id=post.id,
            version=(version_result.scalar() or 0) + 1,
            event_type="rejected",
            message=post.message or "",
            actor_user_id=current_user.id,
            reason=request.reason,
        )
    )
    await db.commit()
    await db.refresh(post)
    return post


@router.get(
    "/scheduled",
    response_model=List[PostRead],
    dependencies=[Depends(require_roles(*CONTENT_EDITOR_ROLES))],
)
async def list_scheduled_posts(
    page_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    query = select(Post).where(Post.status == "scheduled").order_by(Post.scheduled_for)
    if page_id is not None:
        query = query.where(Post.page_id == page_id)
    result = await db.execute(query)
    return result.scalars().all()


@router.post(
    "/{post_id}/schedule",
    response_model=PostRead,
    dependencies=[Depends(require_roles(*CONTENT_EDITOR_ROLES))],
)
async def schedule_approved_post(
    post_id: int,
    request: PostScheduleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Post).where(Post.id == post_id))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.status not in {"approved", "scheduled"}:
        raise HTTPException(status_code=409, detail="Only approved posts can be scheduled")
    scheduled_for = request.scheduled_for.astimezone(timezone.utc)
    if scheduled_for <= datetime.now(timezone.utc):
        raise HTTPException(status_code=422, detail="Scheduled time must be in the future")
    post.status = "scheduled"
    post.scheduled_for = scheduled_for.replace(tzinfo=None)
    version_result = await db.execute(
        select(func.max(PostContentVersion.version)).where(
            PostContentVersion.post_id == post.id
        )
    )
    db.add(
        PostContentVersion(
            post_id=post.id,
            version=(version_result.scalar() or 0) + 1,
            event_type="scheduled",
            message=post.message or "",
            actor_user_id=current_user.id,
            reason=scheduled_for.isoformat(),
        )
    )
    await db.commit()
    await db.refresh(post)
    return post


@router.delete(
    "/{post_id}/schedule",
    response_model=PostRead,
    dependencies=[Depends(require_roles(*CONTENT_EDITOR_ROLES))],
)
async def cancel_post_schedule(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Post).where(Post.id == post_id))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.status != "scheduled":
        raise HTTPException(status_code=409, detail="Only scheduled posts can be cancelled")
    post.status = "approved"
    post.scheduled_for = None
    version_result = await db.execute(
        select(func.max(PostContentVersion.version)).where(
            PostContentVersion.post_id == post.id
        )
    )
    db.add(
        PostContentVersion(
            post_id=post.id,
            version=(version_result.scalar() or 0) + 1,
            event_type="schedule_cancelled",
            message=post.message or "",
            actor_user_id=current_user.id,
        )
    )
    await db.commit()
    await db.refresh(post)
    return post


@router.get(
    "/history",
    dependencies=[Depends(require_roles(*CONTENT_EDITOR_ROLES))],
)
async def get_content_history(
    page_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    runs_query = select(ContentGenerationRun).order_by(
        ContentGenerationRun.started_at.desc()
    )
    versions_query = (
        select(PostContentVersion)
        .join(Post, Post.id == PostContentVersion.post_id)
        .order_by(PostContentVersion.created_at.desc())
    )
    if page_id is not None:
        runs_query = runs_query.where(ContentGenerationRun.page_id == page_id)
        versions_query = versions_query.where(Post.page_id == page_id)
    runs = (await db.execute(runs_query.limit(100))).scalars().all()
    versions = (await db.execute(versions_query.limit(200))).scalars().all()
    return {
        "generation_runs": [
            ContentGenerationRunRead.model_validate(run).model_dump(mode="json")
            for run in runs
        ],
        "content_versions": [
            PostContentVersionRead.model_validate(version).model_dump(mode="json")
            for version in versions
        ],
    }


@router.post(
    "/{post_id}/publish",
    response_model=PostRead,
    dependencies=[Depends(require_roles(*CONTENT_EDITOR_ROLES))],
)
async def publish_draft(
    post_id: int,
    pub_req: PostPublishRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Publish an AI-generated draft post to Facebook."""
    res = await db.execute(select(Post).options(selectinload(Post.page)).where(Post.id == post_id))
    post = res.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if settings.SIMULATION_MODE:
        raise HTTPException(
            status_code=409,
            detail="Live Facebook publishing is disabled while SIMULATION_MODE is enabled.",
        )
    if post.status not in {"approved", "scheduled"}:
        raise HTTPException(status_code=409, detail="Approve this draft before publishing")
    if not pub_req.confirm_publish:
        raise HTTPException(
            status_code=400,
            detail="Explicit administrator confirmation is required to publish.",
        )
    if not post.page or not post.page.is_connected:
        raise HTTPException(status_code=409, detail="Connect the Facebook Page before publishing.")
    if post.page.token_status != "valid":
        raise HTTPException(
            status_code=409,
            detail="Validate a live Page access token with publishing permissions before publishing.",
        )

    success = await automation_engine.publish_draft_post(
        db=db,
        post=post,
        edited_message=pub_req.edited_message,
        media_url=pub_req.media_url
    )
    if not success:
        if post.status == "pending_verification":
            raise HTTPException(
                status_code=502,
                detail=(
                    "Meta returned a post ID, but the post could not be verified. "
                    "Check the Page before retrying to avoid duplicate posts."
                ),
            )
        raise HTTPException(
            status_code=502,
            detail="Meta did not confirm the post. Review the Action Log before retrying.",
        )

    version_result = await db.execute(
        select(func.max(PostContentVersion.version)).where(
            PostContentVersion.post_id == post.id
        )
    )
    db.add(
        PostContentVersion(
            post_id=post.id,
            version=(version_result.scalar() or 0) + 1,
            event_type="published",
            message=post.message or "",
            actor_user_id=current_user.id,
        )
    )
    await db.commit()
    return post

@router.get("/{post_id}", response_model=PostRead)
async def get_post(post_id: int, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Post).where(Post.id == post_id))
    post = res.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post

@router.post(
    "/{post_id}/toggle-monitoring",
    dependencies=[Depends(require_roles(*CONTENT_EDITOR_ROLES))],
)
async def toggle_monitoring(post_id: int, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Post).where(Post.id == post_id))
    post = res.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    post.is_monitored = not post.is_monitored
    await db.commit()
    await db.refresh(post)
    return {"id": post.id, "is_monitored": post.is_monitored}

@router.delete(
    "/{post_id}",
    dependencies=[Depends(require_roles(*CONTENT_EDITOR_ROLES))],
)
async def delete_post(post_id: int, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Post).where(Post.id == post_id))
    post = res.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    await db.delete(post)
    await db.commit()
    return {"status": "deleted", "id": post_id}
