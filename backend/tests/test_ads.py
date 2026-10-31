import asyncio
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


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


def test_simulated_ad_account_sync_persists_daily_delivery(client):
    _login_as_admin(client)
    account_response = client.get("/api/v1/ads/account")
    sync_response = client.post("/api/v1/ads/sync")
    list_response = client.get("/api/v1/ads/campaigns")

    assert account_response.status_code == 200
    assert account_response.json()["connected"] is True
    assert account_response.json()["simulated"] is True
    assert account_response.json()["currency"] == "NPR"
    assert Decimal(account_response.json()["max_daily_budget"]) == Decimal("5.00")
    assert sync_response.status_code == 200
    assert len(sync_response.json()) == 1
    campaign = sync_response.json()[0]
    assert campaign["meta_campaign_id"] == "sim_campaign_001"
    assert Decimal(campaign["daily_budget"]) == Decimal("5.00")
    assert Decimal(campaign["today_spend"]) == Decimal("0.00")
    assert list_response.json()[0]["impressions"] == 0


def test_daily_budget_has_server_side_five_npr_ceiling(client):
    _login_as_admin(client)
    sync_response = client.post("/api/v1/ads/sync")
    assert sync_response.status_code == 200
    campaign_id = sync_response.json()[0]["meta_campaign_id"]

    too_high = client.patch(
        f"/api/v1/ads/campaigns/{campaign_id}/budget",
        json={"daily_budget": "5.01"},
    )
    accepted = client.patch(
        f"/api/v1/ads/campaigns/{campaign_id}/budget",
        json={"daily_budget": "4.50"},
    )

    assert too_high.status_code == 422
    assert accepted.status_code == 200
    assert Decimal(accepted.json()["daily_budget"]) == Decimal("4.50")


def test_campaign_activation_requires_capped_daily_budget(client, monkeypatch):
    from app.services.meta_ads_client import meta_ads_client

    _login_as_admin(client)
    sync_response = client.post("/api/v1/ads/sync")
    assert sync_response.status_code == 200
    campaign_id = sync_response.json()[0]["meta_campaign_id"]
    async def get_over_budget_campaign(campaign_id):
        return {
            "id": campaign_id,
            "daily_budget": "501",
            "lifetime_budget": None,
        }

    monkeypatch.setattr(meta_ads_client, "get_campaign", get_over_budget_campaign)

    response = client.patch(
        f"/api/v1/ads/campaigns/{campaign_id}/status",
        json={"status": "ACTIVE"},
    )
    assert response.status_code == 409


def test_ads_mutations_require_administrator(client):
    admin = client.post(
        "/api/v1/auth/login",
        json={
            "email": "phase-two-admin@example.com",
            "password": "A-strong-test-password-123",
        },
    )
    client.headers["Authorization"] = f"Bearer {admin.json()['access_token']}"
    viewer = client.post(
        "/api/v1/auth/register",
        json={
            "email": "ads-viewer@example.com",
            "password": "Another-strong-password-123",
            "role": "viewer",
        },
    )
    assert viewer.status_code == 201
    login_viewer = client.post(
        "/api/v1/auth/login",
        json={
            "email": "ads-viewer@example.com",
            "password": "Another-strong-password-123",
        },
    )
    client.headers["Authorization"] = f"Bearer {login_viewer.json()['access_token']}"

    response = client.post("/api/v1/ads/sync")
    assert response.status_code == 403


def test_campaign_status_schema_only_accepts_active_or_paused():
    from app.schemas.schemas import AdCampaignStatusUpdate

    assert AdCampaignStatusUpdate(status="paused").status == "PAUSED"
    with pytest.raises(ValidationError):
        AdCampaignStatusUpdate(status="DELETED")


def test_production_seeding_does_not_create_demo_page(monkeypatch):
    from app.config import settings
    from app.core.database import Base
    from app.db import init_db
    from app.models.entities import FacebookPage, RestrictedKeyword

    async def verify_production_seed():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        monkeypatch.setattr(init_db, "AsyncSessionLocal", session_factory)
        monkeypatch.setattr(settings, "ENVIRONMENT", "production")
        monkeypatch.setattr(settings, "INITIAL_ADMIN_EMAIL", "")
        monkeypatch.setattr(settings, "INITIAL_ADMIN_PASSWORD", "")
        await init_db.seed_data()

        async with session_factory() as session:
            page_count = await session.scalar(select(func.count()).select_from(FacebookPage))
            keyword_count = await session.scalar(
                select(func.count()).select_from(RestrictedKeyword)
            )
        await engine.dispose()
        assert page_count == 0
        assert keyword_count > 0

    asyncio.run(verify_production_seed())
