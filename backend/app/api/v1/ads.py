from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user, require_roles
from app.config import settings
from app.core.database import get_db
from app.models.entities import AdCampaign, ActionLog, ActionStatus, UserRole
from app.schemas.schemas import (
    AdAccountRead,
    AdBudgetUpdate,
    AdCampaignRead,
    AdCampaignStatusUpdate,
)
from app.services.ads_manager import sync_campaign_delivery
from app.services.meta_ads_client import MetaAdsError, meta_ads_client

router = APIRouter(
    prefix="/ads",
    tags=["Advertising & Campaign Delivery"],
    dependencies=[Depends(get_current_user)],
)
ADMIN_ROLES = (UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ADMIN)
MAX_DAILY_BUDGET = Decimal("5.00")
MAX_DAILY_BUDGET_MINOR = 500


def _read_campaign(campaign: AdCampaign) -> AdCampaignRead:
    return AdCampaignRead(
        meta_campaign_id=campaign.meta_campaign_id,
        ad_account_id=campaign.ad_account_id,
        name=campaign.name,
        objective=campaign.objective,
        status=campaign.status,
        effective_status=campaign.effective_status,
        daily_budget=(
            Decimal(campaign.daily_budget_minor) / 100
            if campaign.daily_budget_minor is not None
            else None
        ),
        lifetime_budget=(
            Decimal(campaign.lifetime_budget_minor) / 100
            if campaign.lifetime_budget_minor is not None
            else None
        ),
        currency=campaign.currency,
        today_spend=Decimal(campaign.spend_minor or 0) / 100,
        impressions=campaign.impressions or 0,
        clicks=campaign.clicks or 0,
        delivery_date=campaign.delivery_date,
        last_synced_at=campaign.last_synced_at,
    )


def _to_http_error(error: MetaAdsError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=str(error),
    )


@router.get("/account", response_model=AdAccountRead)
async def get_ad_account():
    configured = settings.SIMULATION_MODE or bool(
        settings.META_AD_ACCOUNT_ID and settings.META_AD_ACCESS_TOKEN
    )
    if not configured:
        return AdAccountRead(
            currency=settings.META_AD_CURRENCY,
            configured=False,
            connected=False,
            simulated=False,
            max_daily_budget=MAX_DAILY_BUDGET,
            message="Configure META_AD_ACCOUNT_ID and META_AD_ACCESS_TOKEN to connect an authorized account.",
        )
    try:
        account = await meta_ads_client.get_account()
    except MetaAdsError as exc:
        raise _to_http_error(exc) from exc
    return AdAccountRead(
        account_id=str(account.get("id")) if account.get("id") else None,
        name=account.get("name"),
        currency=str(account.get("currency") or settings.META_AD_CURRENCY),
        configured=True,
        connected=True,
        simulated=bool(account.get("simulated")),
        max_daily_budget=MAX_DAILY_BUDGET,
        message=(
            "Simulation account; changes do not affect Meta."
            if account.get("simulated")
            else "Authorized Meta Ad Account connected."
        ),
    )


@router.get("/campaigns", response_model=List[AdCampaignRead])
async def list_campaigns(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AdCampaign).order_by(AdCampaign.name, AdCampaign.meta_campaign_id)
    )
    return [_read_campaign(campaign) for campaign in result.scalars().all()]


@router.post(
    "/sync",
    response_model=List[AdCampaignRead],
    dependencies=[Depends(require_roles(*ADMIN_ROLES))],
)
async def sync_campaigns(db: AsyncSession = Depends(get_db)):
    try:
        campaigns = await sync_campaign_delivery(db)
    except MetaAdsError as exc:
        db.add(
            ActionLog(
                action_type="ad_delivery_sync",
                status=ActionStatus.FAILED,
                error_message=str(exc),
            )
        )
        await db.commit()
        raise _to_http_error(exc) from exc
    return [_read_campaign(campaign) for campaign in campaigns]


@router.patch(
    "/campaigns/{campaign_id}/budget",
    response_model=AdCampaignRead,
    dependencies=[Depends(require_roles(*ADMIN_ROLES))],
)
async def update_campaign_budget(
    campaign_id: str,
    request: AdBudgetUpdate,
    db: AsyncSession = Depends(get_db),
):
    campaign = await _get_campaign(db, campaign_id)
    await _ensure_account_ownership(campaign)
    if campaign.lifetime_budget_minor is not None:
        raise HTTPException(
            status_code=409,
            detail="Lifetime-budget campaigns cannot be changed through the daily-budget control.",
        )
    budget_minor = int(request.daily_budget * 100)
    if budget_minor > MAX_DAILY_BUDGET_MINOR:
        raise HTTPException(
            status_code=422,
            detail="Daily campaign budget cannot exceed NPR 5.00.",
        )
    try:
        await meta_ads_client.get_account()
        remote_campaign = await meta_ads_client.get_campaign(campaign_id)
        if remote_campaign.get("lifetime_budget") is not None:
            raise HTTPException(
                status_code=409,
                detail="Lifetime-budget campaigns cannot be changed through the daily-budget control.",
            )
        await meta_ads_client.update_budget(campaign_id, budget_minor)
    except MetaAdsError as exc:
        raise _to_http_error(exc) from exc

    campaign.daily_budget_minor = budget_minor
    db.add(
        ActionLog(
            action_type="ad_campaign_budget_updated",
            status=ActionStatus.SUCCESS,
            details={
                "campaign_id": campaign_id,
                "daily_budget_minor": budget_minor,
                "currency": settings.META_AD_CURRENCY,
                "simulated": settings.SIMULATION_MODE,
            },
        )
    )
    await db.commit()
    await db.refresh(campaign)
    return _read_campaign(campaign)


@router.patch(
    "/campaigns/{campaign_id}/status",
    response_model=AdCampaignRead,
    dependencies=[Depends(require_roles(*ADMIN_ROLES))],
)
async def update_campaign_status(
    campaign_id: str,
    request: AdCampaignStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    campaign = await _get_campaign(db, campaign_id)
    await _ensure_account_ownership(campaign)
    try:
        await meta_ads_client.get_account()
        if request.status == "ACTIVE":
            remote_campaign = await meta_ads_client.get_campaign(campaign_id)
            lifetime_budget = remote_campaign.get("lifetime_budget")
            daily_budget = remote_campaign.get("daily_budget")
            if lifetime_budget is not None:
                raise HTTPException(
                    status_code=409,
                    detail="Campaign activation is blocked for lifetime-budget campaigns.",
                )
            try:
                remote_daily_budget = int(daily_budget)
            except (TypeError, ValueError):
                remote_daily_budget = 0
            if not 0 < remote_daily_budget <= MAX_DAILY_BUDGET_MINOR:
                raise HTTPException(
                    status_code=409,
                    detail="Set a campaign-level daily budget from NPR 0.01 to NPR 5.00 before activation.",
                )
        await meta_ads_client.update_status(campaign_id, request.status)
    except MetaAdsError as exc:
        raise _to_http_error(exc) from exc

    campaign.status = request.status
    campaign.effective_status = request.status
    db.add(
        ActionLog(
            action_type="ad_campaign_status_updated",
            status=ActionStatus.SUCCESS,
            details={
                "campaign_id": campaign_id,
                "status": request.status,
                "daily_budget_ceiling_npr": str(MAX_DAILY_BUDGET),
                "simulated": settings.SIMULATION_MODE,
            },
        )
    )
    await db.commit()
    await db.refresh(campaign)
    return _read_campaign(campaign)


async def _get_campaign(db: AsyncSession, campaign_id: str) -> AdCampaign:
    result = await db.execute(
        select(AdCampaign).where(AdCampaign.meta_campaign_id == campaign_id)
    )
    campaign = result.scalar_one_or_none()
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found; sync the Ad Account first.")
    return campaign


async def _ensure_account_ownership(campaign: AdCampaign) -> None:
    configured_account_id = settings.META_AD_ACCOUNT_ID.removeprefix("act_")
    if settings.SIMULATION_MODE:
        return
    if not configured_account_id or campaign.ad_account_id != configured_account_id:
        raise HTTPException(status_code=403, detail="Campaign is not in the configured Ad Account.")
