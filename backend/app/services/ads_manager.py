from datetime import date, datetime, timezone
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.entities import AdCampaign, AdCampaignDailyDelivery, ActionLog, ActionStatus
from app.services.meta_ads_client import (
    MetaAdsError,
    currency_to_minor_units,
    meta_ads_client,
    parse_meta_budget_minor,
)


def _account_id() -> str:
    return settings.META_AD_ACCOUNT_ID.removeprefix("act_") or "simulated"


async def sync_campaign_delivery(db: AsyncSession) -> List[AdCampaign]:
    """Fetch current campaign delivery and persist one updatable daily snapshot."""
    account = await meta_ads_client.get_account()
    account_id = str(account["id"]).removeprefix("act_")
    rows = await meta_ads_client.list_campaigns()
    today = date.today()
    synced_at = datetime.now(timezone.utc)
    persisted: List[AdCampaign] = []

    for row in rows:
        campaign_id = str(row.get("id") or "")
        if not campaign_id:
            raise MetaAdsError("Meta returned a campaign without an ID")
        currency = str(row.get("currency") or account.get("currency") or "")
        if currency != settings.META_AD_CURRENCY:
            raise MetaAdsError("Campaign currency does not match the configured budget currency")
        campaign_result = await db.execute(
            select(AdCampaign).where(AdCampaign.meta_campaign_id == campaign_id)
        )
        campaign = campaign_result.scalar_one_or_none()
        if campaign is None:
            campaign = AdCampaign(
                meta_campaign_id=campaign_id,
                ad_account_id=account_id,
                name=str(row.get("name") or campaign_id),
                status=str(row.get("status") or "PAUSED"),
                currency=currency,
            )
            db.add(campaign)

        delivery_date = today
        raw_date = row.get("date_start")
        if raw_date:
            try:
                delivery_date = date.fromisoformat(str(raw_date))
            except ValueError as exc:
                raise MetaAdsError("Meta returned an invalid campaign delivery date") from exc

        spend_minor = currency_to_minor_units(row.get("spend", "0")) or 0
        impressions = _to_nonnegative_int(row.get("impressions", 0), "impressions")
        clicks = _to_nonnegative_int(row.get("clicks", 0), "clicks")
        campaign.ad_account_id = account_id
        campaign.name = str(row.get("name") or campaign.name)
        campaign.objective = row.get("objective")
        campaign.status = str(row.get("status") or campaign.status)
        campaign.effective_status = row.get("effective_status")
        campaign.daily_budget_minor = parse_meta_budget_minor(row.get("daily_budget"))
        campaign.lifetime_budget_minor = parse_meta_budget_minor(row.get("lifetime_budget"))
        campaign.currency = currency
        campaign.spend_minor = spend_minor
        campaign.impressions = impressions
        campaign.clicks = clicks
        campaign.delivery_date = delivery_date
        campaign.last_synced_at = synced_at

        delivery_result = await db.execute(
            select(AdCampaignDailyDelivery).where(
                AdCampaignDailyDelivery.meta_campaign_id == campaign_id,
                AdCampaignDailyDelivery.delivery_date == delivery_date,
            )
        )
        delivery = delivery_result.scalar_one_or_none()
        if delivery is None:
            delivery = AdCampaignDailyDelivery(
                meta_campaign_id=campaign_id,
                delivery_date=delivery_date,
            )
            db.add(delivery)
        delivery.spend_minor = spend_minor
        delivery.impressions = impressions
        delivery.clicks = clicks
        delivery.actions = row.get("actions") or []
        persisted.append(campaign)

    db.add(
        ActionLog(
            action_type="ad_delivery_sync",
            status=ActionStatus.SUCCESS,
            details={
                "account_id": account_id,
                "campaign_count": len(persisted),
                "simulated": bool(account.get("simulated")),
            },
        )
    )
    await db.commit()
    for campaign in persisted:
        await db.refresh(campaign)
    return persisted


def _to_nonnegative_int(value: Any, label: str) -> int:
    try:
        parsed = int(value or 0)
    except (TypeError, ValueError) as exc:
        raise MetaAdsError(f"Meta returned invalid {label}") from exc
    if parsed < 0:
        raise MetaAdsError(f"Meta returned invalid {label}")
    return parsed
