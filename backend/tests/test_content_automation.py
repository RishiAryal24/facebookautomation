from datetime import datetime, timedelta, timezone
import asyncio
import pytest


def _login_as_admin(client):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "phase-two-admin@example.com",
            "password": "A-strong-test-password-123",
        },
    )
    assert response.status_code == 200
    client.headers["Authorization"] = f"Bearer {response.json()['access_token']}"


def _generate(client, *, request_id, topic="Brand automation"):
    return client.post(
        "/api/v1/posts/generate-draft",
        json={
            "page_id": 1,
            "topic": topic,
            "language": "en",
            "category": "AI and automation",
            "request_id": request_id,
        },
    )


def test_generate_now_persists_draft_and_request_id_is_idempotent(client, monkeypatch):
    from app.services.gemini_service import gemini_service

    calls = []

    async def generate_post(**kwargs):
        calls.append(kwargs)
        return {
            "message": "Thoughtful AI automation can help teams focus on their work. #PyLoom",
            "media_url": None,
            "source": "gemini_api",
        }

    monkeypatch.setattr(gemini_service, "generate_social_post", generate_post)
    _login_as_admin(client)
    generated = _generate(client, request_id="stable-content-request")

    assert generated.status_code == 200
    draft = generated.json()
    assert draft["status"] == "draft"
    assert draft["content_category"] == "AI and automation"
    assert draft["content_language"] == "en"
    assert draft["message"].endswith("#PyLoom")

    repeated = _generate(client, request_id="stable-content-request")
    assert repeated.status_code == 200
    assert repeated.json()["id"] == draft["id"]
    assert len(calls) == 1


@pytest.mark.parametrize("language", ["en", "ne", "bilingual"])
def test_generate_now_passes_selected_language_to_gemini(client, monkeypatch, language):
    from app.services.gemini_service import gemini_service

    calls = []

    async def generate_post(**kwargs):
        calls.append(kwargs)
        return {
            "message": f"Fresh {language} draft text. #PyLoom",
            "media_url": None,
            "source": "gemini_api",
        }

    monkeypatch.setattr(gemini_service, "generate_social_post", generate_post)
    _login_as_admin(client)
    response = client.post(
        "/api/v1/posts/generate-draft",
        json={
            "page_id": 1,
            "topic": "Language coverage",
            "language": language,
            "request_id": f"language-{language}",
        },
    )

    assert response.status_code == 200
    assert response.json()["content_language"] == language
    assert calls[0]["language"] == language


def test_content_settings_are_persisted_and_auto_publish_is_forced_off(client):
    _login_as_admin(client)
    current = client.get("/api/v1/posts/automation-config", params={"page_id": 1})
    assert current.status_code == 200
    assert current.json()["generation_time"] == "09:00"
    assert current.json()["timezone"] == "Asia/Kathmandu"
    assert current.json()["approval_required"] is True
    assert current.json()["auto_publish_enabled"] is False

    updated = client.put(
        "/api/v1/posts/automation-config",
        params={"page_id": 1},
        json={
            "enabled": False,
            "generation_time": "10:30",
            "timezone": "Asia/Kathmandu",
            "posts_per_cycle": 2,
            "languages": ["en", "ne"],
            "categories": ["AI and automation", "Technology trends"],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["enabled"] is False
    assert updated.json()["generation_time"] == "10:30"
    assert updated.json()["posts_per_cycle"] == 2
    assert updated.json()["auto_publish_enabled"] is False


def test_draft_edit_regenerate_approve_reject_and_history(client, monkeypatch):
    from app.services.gemini_service import gemini_service

    async def generate_post(**kwargs):
        return {"message": "A new accurate PyLoom caption. #Technology", "media_url": None, "source": "gemini_api"}

    monkeypatch.setattr(gemini_service, "generate_social_post", generate_post)
    _login_as_admin(client)
    created = _generate(client, request_id="workflow-request")
    assert created.status_code == 200
    post_id = created.json()["id"]

    edited = client.put(
        f"/api/v1/posts/{post_id}/draft",
        json={"message": "Edited caption with a truthful call to action. #PyLoom"},
    )
    assert edited.status_code == 200
    regenerated = client.post(f"/api/v1/posts/{post_id}/regenerate")
    assert regenerated.status_code == 200
    assert regenerated.json()["message"] == "A new accurate PyLoom caption. #Technology"

    approved = client.post(f"/api/v1/posts/{post_id}/approve")
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["approved_by_user_id"] is not None
    assert client.post(f"/api/v1/posts/{post_id}/approve").status_code == 409

    rejected = _generate(client, request_id="reject-request", topic="Customer engagement")
    assert rejected.status_code == 200
    rejected_response = client.post(
        f"/api/v1/posts/{rejected.json()['id']}/reject",
        json={"reason": "Needs a clearer factual basis"},
    )
    assert rejected_response.status_code == 200
    assert rejected_response.json()["status"] == "rejected"
    assert rejected_response.json()["rejection_reason"] == "Needs a clearer factual basis"

    history = client.get("/api/v1/posts/history", params={"page_id": 1})
    assert history.status_code == 200
    events = [entry["event_type"] for entry in history.json()["content_versions"]]
    assert {"generated", "edited", "regenerated", "approved", "rejected"} <= set(events)


def test_approved_draft_schedule_can_be_modified_and_cancelled(client, monkeypatch):
    from app.services.gemini_service import gemini_service

    async def generate_post(**kwargs):
        return {"message": "Useful and accurate content for local teams. #PyLoom", "media_url": None, "source": "gemini_api"}

    monkeypatch.setattr(gemini_service, "generate_social_post", generate_post)
    _login_as_admin(client)
    generated = _generate(client, request_id="schedule-request")
    post_id = generated.json()["id"]
    assert client.post(f"/api/v1/posts/{post_id}/approve").status_code == 200

    first_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    first_schedule = client.post(
        f"/api/v1/posts/{post_id}/schedule",
        json={"scheduled_for": first_time},
    )
    assert first_schedule.status_code == 200
    assert first_schedule.json()["status"] == "scheduled"
    assert first_schedule.json()["published_at"] is None

    updated_time = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    updated_schedule = client.post(
        f"/api/v1/posts/{post_id}/schedule",
        json={"scheduled_for": updated_time},
    )
    assert updated_schedule.status_code == 200
    assert updated_schedule.json()["scheduled_for"] != first_schedule.json()["scheduled_for"]

    upcoming = client.get("/api/v1/posts/scheduled", params={"page_id": 1})
    assert any(item["id"] == post_id for item in upcoming.json())
    cancelled = client.delete(f"/api/v1/posts/{post_id}/schedule")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "approved"
    assert cancelled.json()["scheduled_for"] is None


def test_regeneration_failure_preserves_existing_draft(client, monkeypatch):
    from app.services.gemini_service import GeminiServiceError, gemini_service

    async def generate_initial(**kwargs):
        return {"message": "Existing saved content must survive.", "media_url": None, "source": "gemini_api"}

    async def fail_regeneration(**kwargs):
        raise GeminiServiceError("Gemini request failed")

    monkeypatch.setattr(gemini_service, "generate_social_post", generate_initial)
    _login_as_admin(client)
    created = _generate(client, request_id="preserve-request")
    post_id = created.json()["id"]

    monkeypatch.setattr(gemini_service, "generate_social_post", fail_regeneration)
    failed = client.post(f"/api/v1/posts/{post_id}/regenerate")
    assert failed.status_code == 503
    saved = client.get(f"/api/v1/posts/{post_id}")
    assert saved.status_code == 200
    assert saved.json()["message"] == "Existing saved content must survive."
    assert saved.json()["status"] == "draft"


def test_scheduled_generation_is_idempotent_and_draft_only(monkeypatch):
    from app.core.database import AsyncSessionLocal
    from app.models.entities import ContentGenerationConfig, ContentGenerationRun, FacebookPage
    from app.services.scheduler import _schedule_page_content
    from sqlalchemy import select

    calls = []

    async def generate_draft(**kwargs):
        calls.append(kwargs)
        kwargs["generation_run"].status = "completed"
        kwargs["generation_run"].completed_at = datetime.now(timezone.utc)
        await kwargs["db"].commit()

    monkeypatch.setattr("app.services.scheduler.automation_engine.generate_daily_post", generate_draft)

    async def check_twice():
        async with AsyncSessionLocal() as db:
            config_result = await db.execute(
                select(ContentGenerationConfig).where(ContentGenerationConfig.page_id == 1)
            )
            config = config_result.scalar_one()
            page_result = await db.execute(select(FacebookPage).where(FacebookPage.id == 1))
            page = page_result.scalar_one()
            previous_page_state = (page.token_status, page.meta_page_id)
            page.token_status = "valid"
            page.meta_page_id = "123456789012345"
            config.enabled = True
            config.frequency = "daily"
            config.generation_time = "09:00"
            config.timezone = "Asia/Kathmandu"
            config.posts_per_cycle = 1
            await db.commit()
            due_time = datetime(2026, 10, 30, 4, 30, tzinfo=timezone.utc)
            await _schedule_page_content(db, config, due_time)
            await _schedule_page_content(db, config, due_time)
            result = await db.execute(
                select(ContentGenerationRun).where(
                    ContentGenerationRun.page_id == 1,
                    ContentGenerationRun.run_key == "daily:2026-10-30:0",
                )
            )
            assert result.scalar_one().status == "completed"
            page.token_status, page.meta_page_id = previous_page_state
            await db.commit()

    asyncio.run(check_twice())
    assert len(calls) == 1
    assert calls[0]["allow_auto_publish"] is False


def test_generation_never_publishes_even_if_legacy_auto_publish_flags_are_true(monkeypatch):
    from app.config import settings
    from app.core.database import AsyncSessionLocal
    from app.models.entities import FacebookPage
    from app.services.automation_runner import automation_engine
    from app.services.gemini_service import gemini_service
    from app.services.meta_client import meta_client
    from sqlalchemy import select

    async def generate_post(**kwargs):
        return {"message": "Always save this as a draft. #PyLoom", "media_url": None, "source": "gemini_api"}

    async def publisher_must_not_run(**kwargs):
        raise AssertionError("Draft generation called the Meta publisher")

    monkeypatch.setattr(settings, "SIMULATION_MODE", False)
    monkeypatch.setattr(gemini_service, "generate_social_post", generate_post)
    monkeypatch.setattr(meta_client, "create_page_post", publisher_must_not_run)

    async def generate():
        async with AsyncSessionLocal() as db:
            page_result = await db.execute(select(FacebookPage).where(FacebookPage.id == 1))
            page = page_result.scalar_one()
            page.post_auto_publish = True
            await db.commit()
            post = await automation_engine.generate_daily_post(
                db=db,
                page=page,
                topic="No auto publication",
                language="en",
                auto_publish=True,
                allow_auto_publish=True,
            )
            assert post.status == "draft"

    asyncio.run(generate())
