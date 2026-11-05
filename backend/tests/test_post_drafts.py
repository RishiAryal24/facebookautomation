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


def test_manual_post_generation_saves_editable_draft(client, monkeypatch):
    from app.services.gemini_service import gemini_service

    async def generate_post(**kwargs):
        return {
            "message": "A truthful draft caption.",
            "media_url": None,
            "source": "gemini_api",
        }

    monkeypatch.setattr(gemini_service, "generate_social_post", generate_post)
    _login_as_admin(client)
    response = client.post(
        "/api/v1/posts/generate-draft",
        json={
            "page_id": 1,
            "topic": "Test topic",
            "language": "en",
            "auto_publish": True,
            "include_image": False,
        },
    )

    assert response.status_code == 200
    post = response.json()
    assert post["status"] == "draft"
    assert post["generation_source"] == "gemini_api"

    update_response = client.put(
        f"/api/v1/posts/{post['id']}/draft",
        json={"message": "Reviewed and edited caption.", "media_url": None},
    )
    assert update_response.status_code == 200
    assert update_response.json()["message"] == "Reviewed and edited caption."
    assert update_response.json()["status"] == "draft"


def test_published_posts_cannot_be_edited_or_republished(client):
    _login_as_admin(client)
    posts_response = client.get("/api/v1/posts/")
    assert posts_response.status_code == 200
    published_post = next(post for post in posts_response.json() if post["status"] == "published")

    edit_response = client.put(
        f"/api/v1/posts/{published_post['id']}/draft",
        json={"message": "Not editable"},
    )
    publish_response = client.post(
        f"/api/v1/posts/{published_post['id']}/publish",
        json={},
    )

    assert edit_response.status_code == 409
    assert publish_response.status_code == 409


def test_generation_failure_is_returned_instead_of_fabricating_success(client, monkeypatch):
    from app.config import settings
    from app.services.gemini_service import gemini_service

    _login_as_admin(client)
    monkeypatch.setattr(settings, "ENABLE_LOCAL_AI_FALLBACK", False)
    monkeypatch.setattr(gemini_service, "_client", None)
    response = client.post(
        "/api/v1/posts/generate-draft",
        json={"page_id": 1, "topic": "Test topic", "language": "en", "include_image": False},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Gemini API key is not configured"


def test_publish_endpoint_rejects_simulation_mode_without_calling_meta(client, monkeypatch):
    from app.config import settings
    from app.services.gemini_service import gemini_service
    from app.services.meta_client import meta_client

    async def generate_post(**kwargs):
        return {
            "message": "A test draft that must remain unpublished.",
            "media_url": None,
            "source": "gemini_api",
        }

    async def publisher_must_not_run(**kwargs):
        raise AssertionError("Simulation mode attempted a Meta publish")

    monkeypatch.setattr(settings, "SIMULATION_MODE", True)
    monkeypatch.setattr(gemini_service, "generate_social_post", generate_post)
    monkeypatch.setattr(meta_client, "create_page_post", publisher_must_not_run)
    _login_as_admin(client)
    generated = client.post(
        "/api/v1/posts/generate-draft",
        json={"page_id": 1, "topic": "Test topic", "language": "en", "include_image": False},
    )
    assert generated.status_code == 200
    approved = client.post(f"/api/v1/posts/{generated.json()['id']}/approve")
    assert approved.status_code == 200

    response = client.post(
        f"/api/v1/posts/{generated.json()['id']}/publish",
        json={"confirm_publish": True},
    )

    assert response.status_code == 409
    assert "SIMULATION_MODE" in response.json()["detail"]
    assert client.get(f"/api/v1/posts/{generated.json()['id']}").json()["status"] == "approved"


@pytest.mark.parametrize("with_media", [False, True])
def test_publish_endpoint_marks_post_published_only_after_verified_meta_response(
    client,
    monkeypatch,
    tmp_path,
    with_media,
):
    from app.config import settings
    from app.core.database import AsyncSessionLocal
    from app.models.entities import FacebookPage
    from app.services.gemini_service import gemini_service
    from app.services.media_generation import media_generation_service
    from app.services.meta_client import meta_client
    from sqlalchemy import select

    async def generate_post(**kwargs):
        return {
            "message": "Reviewed post content.",
            "media_url": None,
            "source": "gemini_api",
        }

    async def create_verified_post(*, page_id, message, access_token, media_url=None):
        assert message == "Reviewed post content."
        assert access_token
        assert bool(media_url) is with_media
        return {
            "id": f"123456789_98765432{int(with_media)}",
            "permalink_url": "https://facebook.com/123456789/posts/987654321",
            "verified": True,
        }

    async def set_page_token_status(status):
        from app.core.security import encrypt_token

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(FacebookPage).where(FacebookPage.id == 1))
            page = result.scalar_one()
            previous = (
                page.token_status,
                page.meta_app_id,
                page.access_token_enc,
            )
            if isinstance(status, tuple):
                page.token_status, page.meta_app_id, page.access_token_enc = status
            else:
                page.token_status = status
                page.meta_app_id = settings.META_APP_ID
                page.access_token_enc = encrypt_token("synthetic-live-test-token")
            await db.commit()
            return previous

    monkeypatch.setattr(settings, "SIMULATION_MODE", False)
    monkeypatch.setattr(settings, "MEDIA_STORAGE_DIR", tmp_path)
    monkeypatch.setattr(gemini_service, "generate_social_post", generate_post)
    monkeypatch.setattr(meta_client, "create_page_post", create_verified_post)
    _login_as_admin(client)
    previous_status = asyncio.run(set_page_token_status("valid"))
    try:
        generated = client.post(
            "/api/v1/posts/generate-draft",
            json={"page_id": 1, "topic": "Test topic", "language": "en", "include_image": False},
        )
        assert generated.status_code == 200
        if with_media:
            media = media_generation_service.save_uploaded_image(
                b"\x89PNG\r\n\x1a\nverified-test-image",
                "image/png",
            )
            edited = client.put(
                f"/api/v1/posts/{generated.json()['id']}/draft",
                json={
                    "message": generated.json()["message"],
                    "media_url": media["media_url"],
                },
            )
            assert edited.status_code == 200
        approved = client.post(f"/api/v1/posts/{generated.json()['id']}/approve")
        assert approved.status_code == 200

        response = client.post(
            f"/api/v1/posts/{generated.json()['id']}/publish",
            json={"confirm_publish": True},
        )

        assert response.status_code == 200
        assert response.json()["status"] == "published"
        assert response.json()["meta_post_id"] == f"123456789_98765432{int(with_media)}"
        assert response.json()["is_simulated"] is False
        assert bool(response.json()["media_url"]) is with_media
    finally:
        asyncio.run(set_page_token_status(previous_status))


def test_unverified_meta_post_is_left_pending_and_not_reported_published(
    client,
    monkeypatch,
    tmp_path,
):
    from app.config import settings
    from app.core.database import AsyncSessionLocal
    from app.models.entities import FacebookPage
    from app.services.gemini_service import gemini_service
    from app.services.media_generation import media_generation_service
    from app.services.meta_client import meta_client
    from sqlalchemy import select

    async def generate_post(**kwargs):
        return {
            "message": "Post requiring verification.",
            "media_url": None,
            "source": "gemini_api",
        }

    async def create_unverified_post(**kwargs):
        return {
            "id": "123456789_987654322",
            "permalink_url": None,
            "verified": False,
        }

    async def set_page_token_status(status):
        from app.core.security import encrypt_token

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(FacebookPage).where(FacebookPage.id == 1))
            page = result.scalar_one()
            previous = (
                page.token_status,
                page.meta_app_id,
                page.access_token_enc,
            )
            if isinstance(status, tuple):
                page.token_status, page.meta_app_id, page.access_token_enc = status
            else:
                page.token_status = status
                page.meta_app_id = settings.META_APP_ID
                page.access_token_enc = encrypt_token("synthetic-live-test-token")
            await db.commit()
            return previous

    monkeypatch.setattr(settings, "SIMULATION_MODE", False)
    monkeypatch.setattr(settings, "MEDIA_STORAGE_DIR", tmp_path)
    monkeypatch.setattr(gemini_service, "generate_social_post", generate_post)
    monkeypatch.setattr(meta_client, "create_page_post", create_unverified_post)
    _login_as_admin(client)
    previous_status = asyncio.run(set_page_token_status("valid"))
    try:
        generated = client.post(
            "/api/v1/posts/generate-draft",
            json={"page_id": 1, "topic": "Test topic", "language": "en", "include_image": False},
        )
        assert generated.status_code == 200
        media = media_generation_service.save_uploaded_image(
            b"\x89PNG\r\n\x1a\nunverified-test-image",
            "image/png",
        )
        edited = client.put(
            f"/api/v1/posts/{generated.json()['id']}/draft",
            json={
                "message": generated.json()["message"],
                "media_url": media["media_url"],
            },
        )
        assert edited.status_code == 200
        approved = client.post(f"/api/v1/posts/{generated.json()['id']}/approve")
        assert approved.status_code == 200

        response = client.post(
            f"/api/v1/posts/{generated.json()['id']}/publish",
            json={"confirm_publish": True},
        )

        assert response.status_code == 502
        assert "could not be verified" in response.json()["detail"]
        stored_post = client.get(
            f"/api/v1/posts/{generated.json()['id']}"
        ).json()
        assert stored_post["status"] == "pending_verification"
    finally:
        asyncio.run(set_page_token_status(previous_status))


def test_partial_cross_post_retry_does_not_repeat_confirmed_instagram_publish(
    client,
    monkeypatch,
    tmp_path,
):
    import io
    import uuid

    from PIL import Image

    from app.config import settings
    from app.core.database import AsyncSessionLocal
    from app.core.security import encrypt_token
    from app.models.entities import FacebookPage
    from app.services.gemini_service import gemini_service
    from app.services.media_generation import media_generation_service
    from app.services.meta_client import MetaAPIError, meta_client
    from sqlalchemy import select

    async def generate_post(**kwargs):
        return {
            "message": "Reviewed cross-platform caption.",
            "media_url": None,
            "source": "gemini_api",
        }

    async def set_page_for_test():
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(FacebookPage).where(FacebookPage.id == 1))
            page = result.scalar_one()
            previous = (
                page.token_status,
                page.meta_app_id,
                page.access_token_enc,
                page.instagram_business_account_id,
                page.instagram_username,
            )
            page.token_status = "valid"
            page.meta_app_id = meta_client.app_id
            page.access_token_enc = encrypt_token("synthetic-live-test-token")
            page.instagram_business_account_id = "synthetic-instagram-account"
            page.instagram_username = "pyloom_test"
            await db.commit()
            return previous

    async def restore_page(previous):
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(FacebookPage).where(FacebookPage.id == 1))
            page = result.scalar_one()
            (
                page.token_status,
                page.meta_app_id,
                page.access_token_enc,
                page.instagram_business_account_id,
                page.instagram_username,
            ) = previous
            await db.commit()

    facebook_attempts = []
    instagram_attempts = []
    facebook_post_id = f"987654321_{uuid.uuid4().hex[:12]}"

    async def publish_facebook(**kwargs):
        facebook_attempts.append(kwargs)
        if len(facebook_attempts) == 1:
            raise MetaAPIError("Facebook rejected the test publish", http_status=400)
        return {
            "id": facebook_post_id,
            "permalink_url": f"https://facebook.com/987654321/posts/{facebook_post_id}",
            "verified": True,
        }

    async def publish_instagram(*args, **kwargs):
        instagram_attempts.append((args, kwargs))
        return {
            "id": "instagram-media-123",
            "permalink_url": "https://instagram.com/p/verified/",
            "verified": True,
        }

    monkeypatch.setattr(settings, "SIMULATION_MODE", False)
    monkeypatch.setattr(settings, "MEDIA_STORAGE_DIR", tmp_path)
    monkeypatch.setattr(settings, "MEDIA_PUBLIC_BASE_URL", "https://media.example.com")
    monkeypatch.setattr(meta_client, "app_id", "synthetic-meta-app-id")
    monkeypatch.setattr(gemini_service, "generate_social_post", generate_post)
    monkeypatch.setattr(meta_client, "create_page_post", publish_facebook)
    monkeypatch.setattr(meta_client, "publish_instagram_image", publish_instagram)
    _login_as_admin(client)
    previous_page = asyncio.run(set_page_for_test())
    try:
        generated = client.post(
            "/api/v1/posts/generate-draft",
            json={"page_id": 1, "topic": "Verified test topic", "language": "en", "include_image": False},
        )
        assert generated.status_code == 200
        post_id = generated.json()["id"]
        image_bytes = io.BytesIO()
        Image.new("RGB", (8, 8), "blue").save(image_bytes, format="PNG")
        media = media_generation_service.save_uploaded_image(
            image_bytes.getvalue(),
            "image/png",
        )
        edited = client.put(
            f"/api/v1/posts/{post_id}/draft",
            json={
                "message": generated.json()["message"],
                "media_url": media["media_url"],
            },
        )
        assert edited.status_code == 200
        assert client.post(f"/api/v1/posts/{post_id}/approve").status_code == 200

        first = client.post(
            f"/api/v1/posts/{post_id}/publish",
            json={"confirm_publish": True, "platforms": ["facebook", "instagram"]},
        )
        assert first.status_code == 200
        assert first.json()["status"] == "partially_published"
        assert first.json()["facebook_status"] == "failed"
        assert first.json()["instagram_status"] == "published"

        retry = client.post(
            f"/api/v1/posts/{post_id}/publish",
            json={"confirm_publish": True, "platforms": ["facebook"]},
        )
        assert retry.status_code == 200, retry.text
        assert retry.json()["status"] == "published"
        assert retry.json()["facebook_status"] == "published"
        assert retry.json()["instagram_status"] == "published"
        assert len(facebook_attempts) == 2
        assert len(instagram_attempts) == 1
    finally:
        asyncio.run(restore_page(previous_page))
