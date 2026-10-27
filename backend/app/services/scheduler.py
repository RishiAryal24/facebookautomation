from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.entities import FacebookPage, ActionLog, ActionStatus
from app.services.automation_runner import automation_engine

scheduler = AsyncIOScheduler()

async def check_and_create_daily_posts():
    """Background recurring task that checks and creates scheduled daily posts."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Running automated daily post scheduler check...")
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(FacebookPage).where(FacebookPage.automation_enabled == True))
        pages = res.scalars().all()

        for page in pages:
            target = page.daily_posts_target or 1
            created_today = page.posts_created_today or 0

            # If daily target already reached, skip
            if created_today >= target:
                continue

            # Check operating hours
            if not await automation_engine.is_within_operating_hours(page):
                continue

            current_time = datetime.now().strftime("%H:%M")
            schedule_times = [t.strip() for t in (page.posting_schedule_times or "10:00,18:00").split(",")]

            # Check if current time window matches or if scheduled time passed
            should_post = False
            for scheduled in schedule_times:
                if scheduled:
                    # Allow a +/- 15 minute match window or if target not yet met during the day
                    scheduled_hour = scheduled.split(":")[0] if ":" in scheduled else "10"
                    current_hour = current_time.split(":")[0]
                    if scheduled_hour == current_hour:
                        should_post = True
                        break

            # If should post or we are in active hours and 0 posts have been made today
            if should_post or (created_today == 0 and "10" <= current_time.split(":")[0] <= "21"):
                print(f"Triggering automated daily post for Page: '{page.name}' (Target: {target}, Created: {created_today})")
                try:
                    post = await automation_engine.generate_daily_post(
                        db=db,
                        page=page,
                        topic=page.post_topics_prompt or "Daily product highlights and special offers",
                        language=page.default_language or "ne",
                        tone=page.response_tone or "promotional",
                        auto_publish=page.post_auto_publish # If True posts to FB, if False saves to Drafts queue
                    )
                    print(f"Automated post created successfully! Post ID: {post.id}, Status: {post.status}")
                except Exception as err:
                    print(f"Error in automated daily post for {page.name}: {err}")

async def reset_daily_counters():
    """Resets the posts_created_today counter at midnight."""
    print("Resetting daily post counters for all pages...")
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(FacebookPage))
        pages = res.scalars().all()
        for p in pages:
            p.posts_created_today = 0
        await db.commit()

def start_scheduler():
    """Start APScheduler background workers."""
    if not scheduler.running:
        # Check every 15 minutes for scheduled post creation
        scheduler.add_job(
            check_and_create_daily_posts,
            "interval",
            minutes=15,
            id="daily_post_checker",
            replace_existing=True
        )
        # Reset counters daily at 00:00 midnight
        scheduler.add_job(
            reset_daily_counters,
            "cron",
            hour=0,
            minute=0,
            id="midnight_counter_reset",
            replace_existing=True
        )
        scheduler.start()
        print("APScheduler background worker started successfully (checks every 15 mins).")

def stop_scheduler():
    """Stop APScheduler background workers."""
    if scheduler.running:
        scheduler.shutdown()
        print("APScheduler background worker stopped.")
