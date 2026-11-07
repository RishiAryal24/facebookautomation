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
            "include_image": False,
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
            "include_image": False,
            "request_id": f"language-{language}",
        },
    )

    assert response.status_code == 200
    assert response.json()["content_language"] == language
    assert calls[0]["language"] == language


def test_generate_now_defaults_to_visual_and_persists_missing_product_facts(client, monkeypatch):
    from app.services.gemini_service import gemini_service
    from app.services.media_generation import media_generation_service

    calls = []

    async def generate_post(**kwargs):
        calls.append(kwargs)
        return {
            "message": "A verified-content draft about hospital operations.",
            "image_brief": "A modern, abstract hospital workflow illustration.",
            "missing_facts": [
                "Verified description for PyLoom AI HMS",
                "Approved features for PyLoom AI HMS",
            ],
            "source": "gemini_api",
        }

    async def generate_image(prompt):
        assert "PyLoom AI HMS" in prompt
        assert "modern, abstract hospital workflow illustration" in prompt
        return {"media_url": "/media/generated/verified-test.png", "mime_type": "image/png"}

    monkeypatch.setattr(gemini_service, "generate_social_post", generate_post)
    monkeypatch.setattr(media_generation_service, "generate_image", generate_image)
    _login_as_admin(client)
    response = client.post(
        "/api/v1/posts/generate-draft",
        json={
            "page_id": 1,
            "topic": "PyLoom AI HMS",
            "language": "en",
            "request_id": "visual-product-draft",
        },
    )

    assert response.status_code == 200
    draft = response.json()
    assert draft["media_url"] is None
    assert draft["media_status"] == "queued"
    assert draft["media_brief"] == "A modern, abstract hospital workflow illustration."
    assert draft["content_length"] == "standard"
    assert len(draft["missing_facts"]) == 2
    assert calls[0]["content_length"] == "standard"
    assert calls[0]["brand_profile"]["products"][0]["approved_features"] == []

    from app.services.scheduler import process_pending_media_generation

    assert asyncio.run(process_pending_media_generation()) == 1
    generated = client.get("/api/v1/posts/", params={"page_id": 1})
    image_post = next(item for item in generated.json() if item["id"] == draft["id"])
    assert image_post["media_url"] == "/media/generated/verified-test.png"
    assert image_post["media_status"] == "generated"


def test_generate_now_returns_caption_without_waiting_for_image(client, monkeypatch):
    from app.services.gemini_service import gemini_service
    from app.services.media_generation import media_generation_service

    image_calls = []

    async def generate_post(**kwargs):
        return {
            "message": "A timely and relevant draft caption.",
            "image_brief": "A relevant editorial business visual.",
            "missing_facts": [],
            "source": "gemini_api",
        }

    async def generate_image(prompt):
        image_calls.append(prompt)
        return {"media_url": "/media/generated/concurrent-test.png", "mime_type": "image/png"}

    monkeypatch.setattr(gemini_service, "generate_social_post", generate_post)
    monkeypatch.setattr(media_generation_service, "generate_image", generate_image)
    _login_as_admin(client)
    response = client.post(
        "/api/v1/posts/generate-draft",
        json={
            "page_id": 1,
            "topic": "Concurrent generation topic",
            "language": "en",
            "request_id": "concurrent-generation",
        },
    )

    assert response.status_code == 200
    assert response.json()["message"] == "A timely and relevant draft caption."
    assert response.json()["media_status"] == "queued"
    assert image_calls == []


def test_requested_visual_failure_preserves_caption_as_a_text_only_draft(client, monkeypatch):
    from app.services.gemini_service import gemini_service
    from app.services.media_generation import MediaGenerationError, media_generation_service

    async def generate_post(**kwargs):
        return {
            "message": "A truthful draft that must not be presented as a complete package.",
            "image_brief": "A factual and relevant image concept.",
            "missing_facts": [],
            "source": "gemini_api",
        }

    async def fail_image(prompt):
        raise MediaGenerationError("The configured image-generation provider failed")

    monkeypatch.setattr(gemini_service, "generate_social_post", generate_post)
    monkeypatch.setattr(media_generation_service, "generate_image", fail_image)
    _login_as_admin(client)
    response = client.post(
        "/api/v1/posts/generate-draft",
        json={
            "page_id": 1,
            "topic": "Visual generation failure",
            "language": "en",
            "request_id": "image-failure-request",
        },
    )

    assert response.status_code == 200
    draft = response.json()
    assert draft["message"].startswith("A truthful draft")
    assert draft["media_status"] == "queued"

    from app.services.scheduler import process_pending_media_generation

    assert asyncio.run(process_pending_media_generation()) == 0
    stored = client.get("/api/v1/posts/", params={"page_id": 1})
    failed_draft = next(item for item in stored.json() if item["id"] == draft["id"])
    assert failed_draft["media_status"] == "failed"
    assert failed_draft["media_warning"] == "The configured image-generation provider failed"


def test_content_settings_persist_approval_and_auto_publish_modes(client):
    _login_as_admin(client)
    current = client.get("/api/v1/posts/automation-config", params={"page_id": 1})
    assert current.status_code == 200
    assert current.json()["generation_time"] == "09:00"
    assert current.json()["timezone"] == "Asia/Kathmandu"
    assert current.json()["approval_required"] is True
    assert current.json()["auto_publish_enabled"] is False
    assert current.json()["default_content_length"] == "standard"
    assert current.json()["brand_profile"]["company_name"] == "PyLoom Technologies Pvt. Ltd."

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
            "default_content_length": "detailed",
            "brand_profile": {
                "company_name": "PyLoom Technologies Pvt. Ltd.",
                "products": [
                    {
                        "name": "PyLoom AI HMS",
                        "description": "A verified hospital management product description.",
                        "approved_features": ["Appointment scheduling"],
                    }
                ],
            },
        },
    )
    assert updated.status_code == 200
    assert updated.json()["enabled"] is False
    assert updated.json()["generation_time"] == "10:30"
    assert updated.json()["posts_per_cycle"] == 2
    assert updated.json()["auto_publish_enabled"] is False
    assert updated.json()["default_content_length"] == "detailed"
    assert updated.json()["brand_profile"]["products"][0]["approved_features"] == [
        "Appointment scheduling"
    ]

    auto_publish = client.put(
        "/api/v1/posts/automation-config",
        params={"page_id": 1},
        json={"approval_required": False},
    )
    assert auto_publish.status_code == 200
    assert auto_publish.json()["approval_required"] is False
    assert auto_publish.json()["auto_publish_enabled"] is True
    restored = client.put(
        "/api/v1/posts/automation-config",
        params={"page_id": 1},
        json={"approval_required": True},
    )
    assert restored.status_code == 200


def test_scheduled_generation_auto_publishes_to_facebook_when_approval_is_disabled(
    monkeypatch,
):
    from app.config import settings
    from app.core.database import AsyncSessionLocal
    from app.models.entities import (
        ContentGenerationConfig,
        ContentGenerationRun,
        FacebookPage,
        Post,
    )
    from app.services.scheduler import _schedule_page_content
    from sqlalchemy import select

    calls = []

    async def generate_post(**kwargs):
        db = kwargs["db"]
        run = kwargs["generation_run"]
        post = Post(
            meta_post_id=f"scheduled-test-{run.id}",
            page_id=kwargs["page"].id,
            message="Scheduled Facebook post for automatic publishing.",
            is_ai_generated=True,
            status="draft",
        )
        db.add(post)
        await db.flush()
        run.post_id = post.id
        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(post)
        return post

    async def publish_post(*, db, post, **kwargs):
        calls.append(post)
        assert post.status == "approved"
        assert post.approved_at is not None
        post.status = "published"
        post.facebook_status = "published"
        post.published_at = datetime.now(timezone.utc)
        await db.commit()
        return True

    monkeypatch.setattr(settings, "SIMULATION_MODE", False)
    monkeypatch.setattr(
        "app.services.scheduler.automation_engine.generate_daily_post",
        generate_post,
    )
    monkeypatch.setattr(
        "app.services.scheduler.automation_engine.publish_draft_post",
        publish_post,
    )

    async def run_schedule():
        async with AsyncSessionLocal() as db:
            config = (
                await db.execute(
                    select(ContentGenerationConfig).where(
                        ContentGenerationConfig.page_id == 1
                    )
                )
            ).scalar_one()
            page = (
                await db.execute(select(FacebookPage).where(FacebookPage.id == 1))
            ).scalar_one()
            previous_page_state = (
                page.token_status,
                page.meta_page_id,
                page.is_connected,
            )
            previous_config_state = (
                config.approval_required,
                config.enabled,
                config.timezone,
                config.generation_time,
                config.posts_per_cycle,
            )
            page.token_status = "valid"
            page.meta_page_id = "123456789012345"
            page.is_connected = True
            config.enabled = True
            config.approval_required = False
            config.timezone = "UTC"
            config.generation_time = "00:00"
            config.posts_per_cycle = 1
            await db.commit()

            now = datetime.now(timezone.utc) + timedelta(days=400)
            run_key = f"daily:{now.date().isoformat()}:0"
            await _schedule_page_content(db, config, now)
            run = (
                await db.execute(
                    select(ContentGenerationRun).where(
                        ContentGenerationRun.page_id == 1,
                        ContentGenerationRun.run_key == run_key,
                    )
                )
            ).scalar_one()
            post = await db.get(Post, run.post_id)
            assert run.status == "completed"
            assert post.status == "published"
            assert post.facebook_status == "published"
            assert post.approved_by_user_id is None

            page.token_status, page.meta_page_id, page.is_connected = previous_page_state
            (
                config.approval_required,
                config.enabled,
                config.timezone,
                config.generation_time,
                config.posts_per_cycle,
            ) = previous_config_state
            await db.delete(post)
            await db.delete(run)
            await db.commit()

    asyncio.run(run_schedule())
    assert len(calls) == 1


def test_scheduled_run_retries_stale_generation(monkeypatch):
    from app.core.database import AsyncSessionLocal
    from app.models.entities import ContentGenerationConfig, ContentGenerationRun, FacebookPage
    from app.services.scheduler import _schedule_page_content
    from sqlalchemy import select

    calls = []

    async def generate_draft(**kwargs):
        calls.append(kwargs)
        run = kwargs["generation_run"]
        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        await kwargs["db"].commit()

    monkeypatch.setattr(
        "app.services.scheduler.automation_engine.generate_daily_post",
        generate_draft,
    )

    async def retry_stale():
        async with AsyncSessionLocal() as db:
            config = (
                await db.execute(
                    select(ContentGenerationConfig).where(
                        ContentGenerationConfig.page_id == 1
                    )
                )
            ).scalar_one()
            page = (
                await db.execute(select(FacebookPage).where(FacebookPage.id == 1))
            ).scalar_one()
            previous_page_state = (page.token_status, page.meta_page_id)
            previous_config_state = (
                config.approval_required,
                config.enabled,
                config.timezone,
                config.generation_time,
                config.posts_per_cycle,
            )
            page.token_status = "valid"
            page.meta_page_id = "123456789012345"
            config.enabled = True
            config.approval_required = True
            config.timezone = "UTC"
            config.generation_time = "00:00"
            config.posts_per_cycle = 1
            now = datetime.now(timezone.utc) + timedelta(days=401)
            run_key = f"daily:{now.date().isoformat()}:0"
            run = ContentGenerationRun(
                page_id=page.id,
                run_key=run_key,
                source="scheduled",
                status="in_progress",
                attempt_count=1,
                topic="AI and automation",
                content_category="AI and automation",
                started_at=(now - timedelta(hours=1)).replace(tzinfo=None),
            )
            db.add(run)
            await db.commit()

            await _schedule_page_content(db, config, now)
            await db.refresh(run)
            assert run.status == "completed"
            assert run.attempt_count == 2
            page.token_status, page.meta_page_id = previous_page_state
            (
                config.approval_required,
                config.enabled,
                config.timezone,
                config.generation_time,
                config.posts_per_cycle,
            ) = previous_config_state
            await db.delete(run)
            await db.commit()

    asyncio.run(retry_stale())
    assert len(calls) == 1


def test_scheduled_generation_failure_is_recorded_and_retried(monkeypatch):
    from app.core.database import AsyncSessionLocal
    from app.models.entities import ContentGenerationConfig, ContentGenerationRun, FacebookPage
    from app.services.gemini_service import GeminiServiceError
    from app.services.scheduler import _schedule_page_content
    from sqlalchemy import select

    calls = []

    async def generate_draft(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise GeminiServiceError("Provider temporarily unavailable")
        run = kwargs["generation_run"]
        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        await kwargs["db"].commit()

    monkeypatch.setattr(
        "app.services.scheduler.automation_engine.generate_daily_post",
        generate_draft,
    )

    async def retry_failed_run():
        async with AsyncSessionLocal() as db:
            config = (
                await db.execute(
                    select(ContentGenerationConfig).where(
                        ContentGenerationConfig.page_id == 1
                    )
                )
            ).scalar_one()
            page = (
                await db.execute(select(FacebookPage).where(FacebookPage.id == 1))
            ).scalar_one()
            previous_page_state = (page.token_status, page.meta_page_id)
            previous_config_state = (
                config.approval_required,
                config.enabled,
                config.timezone,
                config.generation_time,
                config.posts_per_cycle,
            )
            page.token_status = "valid"
            page.meta_page_id = "123456789012345"
            config.approval_required = True
            config.enabled = True
            config.timezone = "UTC"
            config.generation_time = "00:00"
            config.posts_per_cycle = 1
            now = datetime.now(timezone.utc) + timedelta(days=402)
            run_key = f"daily:{now.date().isoformat()}:0"
            page_id = page.id
            config_id = config.id
            await _schedule_page_content(db, config, now)
            run = (
                await db.execute(
                    select(ContentGenerationRun).where(
                        ContentGenerationRun.page_id == page_id,
                        ContentGenerationRun.run_key == run_key,
                    )
                )
            ).scalar_one()
            assert run.status == "failed"
            assert run.attempt_count == 1
            run_id = run.id

        async with AsyncSessionLocal() as db:
            config = await db.get(ContentGenerationConfig, config_id)
            page = await db.get(FacebookPage, page_id)
            run = await db.get(ContentGenerationRun, run_id)
            assert config is not None
            assert page is not None
            assert run is not None
            await _schedule_page_content(db, config, now + timedelta(minutes=6))
            await db.refresh(run)
            assert run.status == "completed"
            assert run.attempt_count == 2
            page.token_status, page.meta_page_id = previous_page_state
            (
                config.approval_required,
                config.enabled,
                config.timezone,
                config.generation_time,
                config.posts_per_cycle,
            ) = previous_config_state
            await db.delete(run)
            await db.commit()

    asyncio.run(retry_failed_run())
    assert len(calls) == 2


def test_draft_edit_regenerate_approve_reject_and_history(client, monkeypatch):
    from app.services.gemini_service import gemini_service
    from app.services.media_generation import media_generation_service

    async def generate_post(**kwargs):
        return {
            "message": "A new accurate PyLoom caption. #Technology",
            "image_brief": "Professional business technology visual",
            "missing_facts": [],
            "media_url": None,
            "source": "gemini_api",
        }

    async def generate_image(prompt):
        return {"media_url": "/media/generated/test-image.png", "mime_type": "image/png"}

    monkeypatch.setattr(gemini_service, "generate_social_post", generate_post)
    monkeypatch.setattr(media_generation_service, "generate_image", generate_image)
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
            previous_config_state = (
                config.approval_required,
                config.enabled,
                config.generation_time,
                config.timezone,
            )
            config.enabled = True
            config.approval_required = True
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
            (
                config.approval_required,
                config.enabled,
                config.generation_time,
                config.timezone,
            ) = previous_config_state
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
                include_image=False,
            )
            assert post.status == "draft"

    asyncio.run(generate())
