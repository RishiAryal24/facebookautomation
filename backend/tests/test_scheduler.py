import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.automation_runner import AutomationEngine


def test_operating_hours_use_page_timezone():
    page = SimpleNamespace(
        timezone="America/New_York",
        operating_hours_start="09:00",
        operating_hours_end="17:00",
    )
    engine = AutomationEngine()

    during_hours = asyncio.run(
        engine.is_within_operating_hours(
            page,
            now=datetime(2025, 1, 15, 15, 0, tzinfo=timezone.utc),
        )
    )
    after_hours = asyncio.run(
        engine.is_within_operating_hours(
            page,
            now=datetime(2025, 1, 15, 23, 0, tzinfo=timezone.utc),
        )
    )

    assert during_hours is True
    assert after_hours is False


def test_scheduler_reserves_a_slot_only_once():
    from app.core.database import AsyncSessionLocal
    from app.services.scheduler import _reserve_run

    async def reserve_twice():
        now = datetime.now(timezone.utc)
        scheduled_for = now.replace(microsecond=0, tzinfo=None)
        async with AsyncSessionLocal() as db:
            first = await _reserve_run(db, 1, scheduled_for, now)
            second = await _reserve_run(db, 1, scheduled_for, now)
            return first, second

    first, second = asyncio.run(reserve_twice())
    assert first is not None
    assert first.attempt_count == 1
    assert second is None


def test_token_lifecycle_scheduler_validates_each_page_with_its_own_token(monkeypatch):
    from app.config import settings
    from app.core.database import AsyncSessionLocal
    from app.core.security import encrypt_token
    from app.models.entities import FacebookPage
    from app.services.meta_client import meta_client
    from app.services.scheduler import check_page_token_lifecycle

    page_id = "623456789012345"
    expected_token = "scheduler-page-token"
    received = []

    async def validate(requested_page_id, access_token, *, force_live=False):
        received.append((requested_page_id, access_token, force_live))
        return {
            "status": "valid",
            "expires_at": None,
            "permissions": ["pages_manage_posts", "pages_read_engagement"],
            "tasks": ["CREATE_CONTENT"],
            "meta_app_id": settings.META_APP_ID,
            "page": {"id": requested_page_id, "tasks": ["CREATE_CONTENT"]},
        }

    monkeypatch.setattr(settings, "SIMULATION_MODE", True)
    monkeypatch.setattr(meta_client, "validate_page_credentials", validate)

    async def create_page():
        async with AsyncSessionLocal() as db:
            page = FacebookPage(
                meta_page_id=page_id,
                name="Lifecycle Scheduler Test Page",
                access_token_enc=encrypt_token(expected_token),
                token_status="reauthorization_required",
                meta_app_id=None,
                is_connected=True,
            )
            db.add(page)
            await db.commit()
            return page.id

    async def get_page_status(record_id):
        async with AsyncSessionLocal() as db:
            page = await db.get(FacebookPage, record_id)
            return page.token_status, page.last_validated_at, page.meta_app_id

    async def remove_page(record_id):
        async with AsyncSessionLocal() as db:
            page = await db.get(FacebookPage, record_id)
            if page:
                await db.delete(page)
                await db.commit()

    record_id = asyncio.run(create_page())
    try:
        asyncio.run(check_page_token_lifecycle())
        status, validated_at, app_id = asyncio.run(get_page_status(record_id))
        assert (page_id, expected_token, True) in received
        assert status == "valid"
        assert validated_at is not None
        assert app_id == settings.META_APP_ID
    finally:
        asyncio.run(remove_page(record_id))
