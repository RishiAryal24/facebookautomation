import asyncio

from sqlalchemy import select


def _login_as_admin(client):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "phase-two-admin@example.com",
            "password": "A-strong-test-password-123",
        },
    )
    assert response.status_code == 200
    client.headers["Authorization"] = "Bearer " + response.json()["access_token"]


def _valid_credentials(page_id, *, name="Verified Test Page"):
    return {
        "status": "valid",
        "expires_at": None,
        "permissions": ["pages_manage_posts", "pages_read_engagement"],
        "tasks": ["CREATE_CONTENT"],
        "meta_app_id": "test-meta-app-id",
        "page": {
            "id": page_id,
            "name": name,
            "category": "Business Page",
            "tasks": ["CREATE_CONTENT"],
        },
    }


def test_connect_uses_exact_submitted_token_and_stores_only_encrypted_value(
    client,
    monkeypatch,
):
    from app.config import settings
    from app.core.database import AsyncSessionLocal
    from app.core.security import decrypt_token
    from app.models.entities import FacebookPage
    from app.services.meta_client import meta_client

    page_id = "123456789012345"
    submitted_token = " exact-request-token "
    submitted_user_token = "exact-user-task-token"
    monkeypatch.setattr(settings, "SIMULATION_MODE", True)
    monkeypatch.setattr(settings, "META_APP_ID", "test-meta-app-id")
    received = {}

    async def validate_credentials(
        requested_page_id,
        access_token,
        *,
        user_access_token=None,
        force_live=False,
    ):
        received.update(
            page_id=requested_page_id,
            token=access_token,
            user_token=user_access_token,
            force_live=force_live,
        )
        return _valid_credentials(requested_page_id)

    monkeypatch.setattr(meta_client, "validate_page_credentials", validate_credentials)
    _login_as_admin(client)
    response = client.post(
        "/api/v1/pages/",
        json={
            "meta_page_id": page_id,
            "name": "User-entered name",
            "access_token": submitted_token,
            "user_access_token": submitted_user_token,
            "default_language": "en",
            "response_tone": "professional",
            "brand_context": "Existing client context.",
        },
    )

    assert response.status_code == 200
    assert received == {
        "page_id": page_id,
        "token": submitted_token,
        "user_token": submitted_user_token,
        "force_live": True,
    }
    assert response.json()["token_status"] == "valid"
    assert response.json()["meta_app_id"] == "test-meta-app-id"
    assert response.json()["last_validated_at"]
    assert "access_token" not in response.json()
    assert submitted_token not in response.text
    assert submitted_user_token not in response.text

    async def verify_encrypted_token():
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(FacebookPage).where(FacebookPage.meta_page_id == page_id)
            )
            page = result.scalar_one()
            assert page.access_token_enc != submitted_token
            assert decrypt_token(page.access_token_enc) == submitted_token
            assert page.meta_app_id == "test-meta-app-id"
            assert page.default_language == "en"
            assert not hasattr(page, "user_access_token")
            await db.delete(page)
            await db.commit()

    asyncio.run(verify_encrypted_token())


def test_failed_reconnect_preserves_existing_token_and_page_settings(client, monkeypatch):
    from app.config import settings
    from app.core.database import AsyncSessionLocal
    from app.core.security import decrypt_token
    from app.models.entities import FacebookPage
    from app.services.meta_client import MetaAPIError, meta_client

    page_id = "223456789012345"
    original_token = "original-valid-page-token"
    _login_as_admin(client)

    async def valid(
        requested_page_id,
        access_token,
        *,
        user_access_token=None,
        force_live=False,
    ):
        return _valid_credentials(requested_page_id, name="Actual Page Name")

    monkeypatch.setattr(settings, "META_APP_ID", "test-meta-app-id")
    monkeypatch.setattr(meta_client, "validate_page_credentials", valid)
    initial = client.post(
        "/api/v1/pages/",
        json={
            "meta_page_id": page_id,
            "name": "Page",
            "access_token": original_token,
            "default_language": "ne",
            "brand_context": "Keep these settings.",
        },
    )
    assert initial.status_code == 200
    page_record_id = initial.json()["id"]

    async def reject(
        requested_page_id,
        access_token,
        *,
        user_access_token=None,
        force_live=False,
    ):
        raise MetaAPIError(
            "Meta rejected the replacement token",
            http_status=400,
            meta_error={
                "message": "Error validating access token",
                "code": 190,
                "error_subcode": 463,
            },
        )

    monkeypatch.setattr(meta_client, "validate_page_credentials", reject)
    replacement = client.post(
        "/api/v1/pages/",
        json={
            "meta_page_id": page_id,
            "name": "Should not overwrite",
            "access_token": "expired-replacement-token",
            "default_language": "en",
        },
    )

    assert replacement.status_code == 422
    assert replacement.json()["detail"]["meta_error"]["code"] == 190
    assert replacement.json()["detail"]["meta_error"]["error_subcode"] == 463

    async def verify_original():
        async with AsyncSessionLocal() as db:
            page = await db.get(FacebookPage, page_record_id)
            assert decrypt_token(page.access_token_enc) == original_token
            assert page.name == "Actual Page Name"
            assert page.default_language == "ne"
            assert page.brand_context == "Keep these settings."
            await db.delete(page)
            await db.commit()

    asyncio.run(verify_original())


def test_connect_requires_task_verification_before_storing_page_token(client, monkeypatch):
    from app.core.database import AsyncSessionLocal
    from app.models.entities import FacebookPage
    from app.services.meta_client import meta_client

    page_id = "273456789012345"

    async def valid_page_token_only(requested_page_id, access_token, **kwargs):
        credentials = _valid_credentials(requested_page_id)
        credentials["tasks"] = None
        return credentials

    monkeypatch.setattr(meta_client, "validate_page_credentials", valid_page_token_only)
    _login_as_admin(client)
    response = client.post(
        "/api/v1/pages/",
        json={
            "meta_page_id": page_id,
            "name": "Page without task verification",
            "access_token": "valid-page-token-without-user-token",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["status"] == "task_verification_required"
    assert "CREATE_CONTENT" in response.json()["detail"]["message"]

    async def verify_no_record():
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(FacebookPage).where(FacebookPage.meta_page_id == page_id)
            )
            assert result.scalar_one_or_none() is None

    asyncio.run(verify_no_record())


def test_connection_error_does_not_create_page_or_return_credentials(client, monkeypatch):
    from app.core.database import AsyncSessionLocal
    from app.models.entities import FacebookPage
    from app.services.meta_client import MetaAPIError, meta_client

    page_id = "323456789012345"

    async def reject(
        requested_page_id,
        access_token,
        *,
        user_access_token=None,
        force_live=False,
    ):
        raise MetaAPIError(
            "Meta rejected token",
            http_status=400,
            meta_error={
                "message": "Invalid OAuth access token.",
                "code": 190,
                "error_subcode": 463,
            },
        )

    monkeypatch.setattr(meta_client, "validate_page_credentials", reject)
    _login_as_admin(client)
    response = client.post(
        "/api/v1/pages/",
        json={
            "meta_page_id": page_id,
            "name": "Rejected Page",
            "access_token": "invalid-token-value",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["meta_error"]["message"] == "Invalid OAuth access token."
    assert response.json()["detail"]["meta_error"]["error_subcode"] == 463
    assert "invalid-token-value" not in response.text

    async def verify_no_record():
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(FacebookPage).where(FacebookPage.meta_page_id == page_id)
            )
            assert result.scalar_one_or_none() is None

    asyncio.run(verify_no_record())


def test_read_only_page_token_diagnostic_uses_submitted_token_without_storing_it(
    client,
    monkeypatch,
):
    from app.services.meta_client import meta_client

    page_id = "523456789012345"
    submitted_token = "fresh-form-token-for-diagnostic"
    submitted_user_token = "fresh-form-user-token-for-diagnostic"
    received = {}

    async def diagnose(requested_page_id, access_token, user_access_token=None):
        received.update(
            page_id=requested_page_id,
            token=access_token,
            user_token=user_access_token,
        )
        return {
            "submitted_token_used_unchanged": True,
            "checks": {
                "page_read_without_appsecret_proof": {
                    "success": False,
                    "http_status": 400,
                    "meta_error": {"message": "Read-only failure", "code": 190},
                }
            },
        }

    monkeypatch.setattr(meta_client, "diagnose_page_authentication", diagnose)
    _login_as_admin(client)
    response = client.post(
        "/api/v1/pages/diagnose-token",
        json={
            "meta_page_id": page_id,
            "name": "Diagnostic Page",
            "access_token": submitted_token,
            "user_access_token": submitted_user_token,
        },
    )

    assert response.status_code == 200
    assert received == {
        "page_id": page_id,
        "token": submitted_token,
        "user_token": submitted_user_token,
    }
    assert response.json()["submitted_token_used_unchanged"] is True
    assert submitted_token not in response.text
    assert submitted_user_token not in response.text


def test_multiple_pages_resolve_their_own_tokens(client):
    from app.config import settings
    from app.core.database import AsyncSessionLocal
    from app.core.security import encrypt_token
    from app.models.entities import FacebookPage
    from app.services.meta_client import meta_client

    monkeypatch_app_id = settings.META_APP_ID

    async def add_pages():
        async with AsyncSessionLocal() as db:
            pages = [
                FacebookPage(
                    meta_page_id="423456789012345",
                    name="Page A",
                    access_token_enc=encrypt_token("page-a-token"),
                    token_status="valid",
                    meta_app_id=monkeypatch_app_id,
                    is_connected=True,
                ),
                FacebookPage(
                    meta_page_id="523456789012345",
                    name="Page B",
                    access_token_enc=encrypt_token("page-b-token"),
                    token_status="valid",
                    meta_app_id=monkeypatch_app_id,
                    is_connected=True,
                ),
            ]
            db.add_all(pages)
            await db.commit()
            return [page.id for page in pages]

    async def verify_pages(page_ids):
        async with AsyncSessionLocal() as db:
            first = await db.get(FacebookPage, page_ids[0])
            second = await db.get(FacebookPage, page_ids[1])
            assert meta_client.get_page_access_token(first) == "page-a-token"
            assert meta_client.get_page_access_token(second) == "page-b-token"
            await db.delete(first)
            await db.delete(second)
            await db.commit()

    page_ids = asyncio.run(add_pages())
    asyncio.run(verify_pages(page_ids))
