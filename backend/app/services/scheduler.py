import logging
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import AsyncSessionLocal
from app.models.entities import (
    ActionLog,
    ActionStatus,
    ContentGenerationConfig,
    ContentGenerationRun,
    FacebookPage,
    Post,
    ScheduledPostRun,
)
from app.services.automation_runner import automation_engine
from app.services.ads_manager import sync_campaign_delivery
from app.services.gemini_service import GeminiServiceError
from app.services.meta_client import MetaAPIError, meta_client
from app.services.meta_ads_client import MetaAdsError

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler(timezone=timezone.utc)
RUN_STALE_AFTER = timedelta(minutes=30)
RETRY_BASE_DELAY = timedelta(minutes=5)
TOKEN_EXPIRING_SOON = timedelta(days=7)


def _database_utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


async def _reserve_run(
    db: AsyncSession,
    page_id: int,
    scheduled_for: datetime,
    now_utc: datetime,
) -> ScheduledPostRun | None:
    result = await db.execute(
        select(ScheduledPostRun)
        .where(
            ScheduledPostRun.page_id == page_id,
            ScheduledPostRun.scheduled_for == scheduled_for,
        )
        .with_for_update()
    )
    run = result.scalar_one_or_none()
    if run:
        if run.status in {"completed", "needs_review"}:
            return None
        if run.attempt_count >= settings.SCHEDULER_MAX_ATTEMPTS:
            return None
        last_attempt = run.last_attempt_at or run.started_at
        if run.status == "in_progress" and last_attempt:
            if now_utc - _as_utc(last_attempt) < RUN_STALE_AFTER:
                return None
        elif last_attempt:
            retry_delay = RETRY_BASE_DELAY * run.attempt_count
            if now_utc - _as_utc(last_attempt) < retry_delay:
                return None

        run.status = "in_progress"
        run.attempt_count += 1
        run.last_error = None
        run.started_at = _database_utc(now_utc)
        run.last_attempt_at = _database_utc(now_utc)
        run.completed_at = None
        await db.commit()
        return run

    run = ScheduledPostRun(
        page_id=page_id,
        scheduled_for=scheduled_for,
        status="in_progress",
        attempt_count=1,
        started_at=_database_utc(now_utc),
        last_attempt_at=_database_utc(now_utc),
    )
    db.add(run)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return None
    await db.refresh(run)
    return run


async def _finish_run(
    db: AsyncSession,
    run: ScheduledPostRun,
    *,
    post: Post | None = None,
    error: str | None = None,
    needs_review: bool = False,
) -> None:
    run.status = "needs_review" if needs_review else "failed" if error else "completed"
    run.last_error = error
    run.post_id = post.id if post else None
    run.completed_at = _database_utc(datetime.now(timezone.utc))
    if error:
        db.add(
            ActionLog(
                page_id=run.page_id,
                action_type="scheduled_post_generation",
                status=ActionStatus.FAILED,
                error_message=error,
                details={
                    "scheduled_for": run.scheduled_for.isoformat(),
                    "attempt": run.attempt_count,
                },
            )
        )
    await db.commit()


async def _schedule_page_content(
    db: AsyncSession,
    config: ContentGenerationConfig,
    now_utc: datetime,
) -> None:
    if not config.enabled or config.frequency != "daily":
        return
    try:
        page_timezone = ZoneInfo(config.timezone)
        generation_time = time.fromisoformat(config.generation_time)
    except (ZoneInfoNotFoundError, ValueError):
        logger.error("Skipping content generation for Page %s due to invalid schedule settings", config.page_id)
        return

    local_now = now_utc.astimezone(page_timezone)
    if local_now.timetz().replace(tzinfo=None) < generation_time:
        return

    page_result = await db.execute(select(FacebookPage).where(FacebookPage.id == config.page_id))
    page = page_result.scalar_one_or_none()
    if page is None:
        logger.warning("Skipping content generation for missing Page %s", config.page_id)
        return
    if page.token_status == "simulated" or page.meta_page_id.startswith("pyloom_page_"):
        return

    languages = config.languages or ["en", "ne"]
    categories = config.categories or ["Company promotions"]
    for generation_index in range(config.posts_per_cycle):
        run_key = f"daily:{local_now.date().isoformat()}:{generation_index}"
        existing_result = await db.execute(
            select(ContentGenerationRun).where(
                ContentGenerationRun.page_id == page.id,
                ContentGenerationRun.run_key == run_key,
            )
        )
        existing_run = existing_result.scalar_one_or_none()
        if existing_run:
            continue

        category_index = (local_now.date().toordinal() + generation_index) % len(categories)
        category = categories[category_index]
        language = languages[(local_now.date().toordinal() + generation_index) % len(languages)]
        run = ContentGenerationRun(
            page_id=page.id,
            run_key=run_key,
            source="scheduled",
            status="in_progress",
            topic=category,
            content_category=category,
        )
        db.add(run)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            continue
        await db.refresh(run)

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
        try:
            await automation_engine.generate_daily_post(
                db=db,
                page=page,
                topic=category,
                language=language,
                tone=config.tone,
                auto_publish=False,
                allow_auto_publish=False,
                category=category,
                brand_context="\n".join(
                    item for item in (config.brand_context, page.brand_context) if item
                ),
                recent_messages=recent_messages,
                generation_run=run,
            )
        except (GeminiServiceError, SQLAlchemyError, ValueError) as exc:
            run_id = run.id
            await db.rollback()
            run = await db.get(ContentGenerationRun, run_id)
            if run is None:
                raise
            run.status = "failed"
            run.error_message = str(exc)
            run.completed_at = _database_utc(datetime.now(timezone.utc))
            db.add(
                ActionLog(
                    page_id=page.id,
                    action_type="scheduled_content_generation",
                    status=ActionStatus.FAILED,
                    error_message=str(exc),
                    details={"run_key": run_key, "category": category},
                )
            )
            await db.commit()
            logger.warning("Scheduled content generation failed for Page %s: %s", page.id, exc)


async def check_and_create_daily_posts():
    """Generate due drafts only; scheduled generation never publishes to Facebook."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ContentGenerationConfig).where(ContentGenerationConfig.enabled.is_(True))
        )
        now_utc = datetime.now(timezone.utc)
        for config in result.scalars().all():
            try:
                await _schedule_page_content(db, config, now_utc)
            except (SQLAlchemyError, ValueError, ZoneInfoNotFoundError):
                await db.rollback()
                logger.exception(
                    "Scheduler error while processing Page %s",
                    config.page_id,
                )

async def check_daily_campaign_delivery():
    """Refresh daily Ad Account delivery snapshots when Ads are configured or simulated."""
    if not settings.SIMULATION_MODE and not (
        settings.META_AD_ACCOUNT_ID and settings.META_AD_ACCESS_TOKEN
    ):
        return
    async with AsyncSessionLocal() as db:
        try:
            await sync_campaign_delivery(db)
        except (MetaAdsError, SQLAlchemyError):
            await db.rollback()
            logger.exception("Daily Meta campaign delivery monitoring failed")


async def check_page_token_lifecycle():
    """Revalidate stored real Page credentials and record status transitions."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(FacebookPage).where(
                FacebookPage.is_connected.is_(True),
                FacebookPage.access_token_enc.is_not(None),
                FacebookPage.token_status != "simulated",
            )
        )
        for page in result.scalars().all():
            previous_status = page.token_status
            try:
                token = meta_client.get_page_access_token(
                    page,
                    allow_revalidation=True,
                )
                if token.startswith("mock_"):
                    continue
                credentials = await meta_client.validate_page_credentials(
                    page.meta_page_id,
                    token,
                    force_live=True,
                )
                expires_at = credentials["expires_at"]
                expiring = (
                    expires_at is not None
                    and _as_utc(expires_at) <= datetime.now(timezone.utc) + TOKEN_EXPIRING_SOON
                )
                page.token_status = "expiring_soon" if expiring else "valid"
                page.token_expires_at = expires_at
                page.meta_app_id = credentials.get("meta_app_id", settings.META_APP_ID)
                page.granted_permissions = credentials["permissions"]
                if credentials.get("tasks") is not None:
                    page.page_tasks = credentials["tasks"]
                page.last_validated_at = _database_utc(datetime.now(timezone.utc))
            except MetaAPIError as exc:
                page.token_status = meta_client.validation_failure_status(exc)
                logger.warning(
                    "Page credential validation failed for Page %s (%s): %s",
                    page.id,
                    page.token_status,
                    str(exc),
                )
            if page.token_status != previous_status:
                db.add(
                    ActionLog(
                        page_id=page.id,
                        action_type="page_credential_status",
                        status=(
                            ActionStatus.SUCCESS
                            if page.token_status in {"valid", "expiring_soon"}
                            else ActionStatus.FAILED
                        ),
                        error_message=(
                            None
                            if page.token_status in {"valid", "expiring_soon"}
                            else page.token_status
                        ),
                        details={
                            "previous_status": previous_status,
                            "status": page.token_status,
                            "expires_at": (
                                page.token_expires_at.isoformat()
                                if page.token_expires_at
                                else None
                            ),
                        },
                    )
                )
        await db.commit()


def start_scheduler():
    """Start APScheduler's persistent, non-overlapping recurring checks."""
    if scheduler.running:
        return
    scheduler.add_job(
        check_and_create_daily_posts,
        "interval",
        minutes=5,
        id="daily_post_checker",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )
    scheduler.add_job(
        check_daily_campaign_delivery,
        "interval",
        hours=1,
        id="daily_campaign_delivery_monitor",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=1800,
    )
    scheduler.add_job(
        check_page_token_lifecycle,
        "interval",
        hours=6,
        id="page_token_lifecycle_monitor",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    logger.info("APScheduler started; scheduled post checks run every five minutes")


def stop_scheduler():
    """Stop APScheduler background workers."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")
