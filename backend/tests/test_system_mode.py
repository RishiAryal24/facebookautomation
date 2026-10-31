import asyncio


def _login_as_admin(client):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "phase-two-admin@example.com",
            "password": "A-strong-test-password-123",
        },
    )
    assert response.status_code == 200
    client.headers["Authorization"] = (
        "Bearer " + response.json()["access_token"]
    )


def test_live_mode_is_blocked_until_page_is_validated(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "SIMULATION_MODE", True)
    _login_as_admin(client)

    response = client.put(
        "/api/v1/system/simulation-mode",
        json={"simulation_mode": False},
    )

    assert response.status_code == 409
    assert any("connected Page must have a valid token" in item for item in response.json()["detail"]["blockers"])
    assert settings.SIMULATION_MODE is True


def test_mode_switch_requires_live_permissions_and_page_task(client, monkeypatch):
    from app.config import settings
    from app.core.database import AsyncSessionLocal
    from app.core.security import encrypt_token
    from app.models.entities import FacebookPage

    page_id = "987654321099902"
    monkeypatch.setattr(settings, "SIMULATION_MODE", True)
    _login_as_admin(client)

    async def create_page():
        async with AsyncSessionLocal() as db:
            page = FacebookPage(
                meta_page_id=page_id,
                name="Synthetic Readiness Test Page",
                access_token_enc=encrypt_token("synthetic-test-page-token"),
                token_status="valid",
                meta_app_id=settings.META_APP_ID,
                granted_permissions=[
                    "pages_manage_posts",
                    "pages_read_engagement",
                ],
                page_tasks=["CREATE_CONTENT"],
                is_connected=True,
            )
            db.add(page)
            await db.commit()
            return page.id

    async def delete_page(page_record_id):
        async with AsyncSessionLocal() as db:
            page = await db.get(FacebookPage, page_record_id)
            if page:
                await db.delete(page)
                await db.commit()

    page_record_id = asyncio.run(create_page())
    try:
        readiness = client.get("/api/v1/system/simulation-mode")
        assert readiness.status_code == 200
        assert readiness.json()["live_ready"] is True

        live_response = client.put(
            "/api/v1/system/simulation-mode",
            json={"simulation_mode": False},
        )
        assert live_response.status_code == 200
        assert live_response.json()["simulation_mode"] is False

        trial_response = client.put(
            "/api/v1/system/simulation-mode",
            json={"simulation_mode": True},
        )
        assert trial_response.status_code == 200
        assert trial_response.json()["simulation_mode"] is True
    finally:
        asyncio.run(delete_page(page_record_id))
