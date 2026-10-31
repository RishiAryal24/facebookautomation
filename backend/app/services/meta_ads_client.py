import hashlib
import hmac
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings

class MetaAdsError(RuntimeError):
    """Safe, user-facing Marketing API failure."""


class MetaAdsClient:
    def __init__(self):
        self.base_url = f"https://graph.facebook.com/{settings.META_GRAPH_API_VERSION}"

    def _account_id(self) -> str:
        account_id = settings.META_AD_ACCOUNT_ID.removeprefix("act_") or (
            "0" if settings.SIMULATION_MODE else ""
        )
        if not re.fullmatch(r"\d+", account_id):
            raise MetaAdsError("META_AD_ACCOUNT_ID must be configured as a numeric Ad Account ID")
        return account_id

    def _params(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        token = settings.META_AD_ACCESS_TOKEN
        if not token or token.startswith("mock_"):
            raise MetaAdsError("A valid authorized Marketing API access token is required")
        result = dict(params or {})
        result["access_token"] = token
        if settings.META_APP_SECRET:
            result["appsecret_proof"] = hmac.new(
                settings.META_APP_SECRET.encode(),
                token.encode(),
                hashlib.sha256,
            ).hexdigest()
        return result

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.request(
                    method,
                    f"{self.base_url}/{path.lstrip('/')}",
                    params=params,
                    data=data,
                )
        except httpx.TimeoutException as exc:
            raise MetaAdsError("Meta Marketing API request timed out") from exc
        except httpx.HTTPError as exc:
            raise MetaAdsError("Meta Marketing API request failed") from exc

        try:
            payload = response.json()
        except ValueError:
            payload = {}
        meta_error = payload.get("error") if isinstance(payload, dict) else None
        if not response.is_success or meta_error:
            error_code = meta_error.get("code") if isinstance(meta_error, dict) else None
            suffix = f" (Meta error {error_code})" if error_code else ""
            raise MetaAdsError(
                f"Meta Marketing API request failed with HTTP {response.status_code}{suffix}"
            )
        if not isinstance(payload, dict):
            raise MetaAdsError("Meta Marketing API returned an invalid response")
        return payload

    async def get_account(self) -> Dict[str, Any]:
        account_id = self._account_id()
        if settings.SIMULATION_MODE:
            return {
                "id": f"act_{account_id}",
                "name": "Simulated Ad Account",
                "currency": settings.META_AD_CURRENCY,
                "account_status": 1,
                "simulated": True,
            }
        payload = await self._request_json(
            "GET",
            f"act_{account_id}",
            params=self._params(
                {"fields": "id,name,currency,account_status,timezone_name"}
            ),
        )
        if payload.get("currency") != settings.META_AD_CURRENCY:
            raise MetaAdsError(
                f"Ad Account currency must be {settings.META_AD_CURRENCY} "
                f"to enforce the configured daily budget ceiling"
            )
        payload["simulated"] = False
        return payload

    async def list_campaigns(self) -> List[Dict[str, Any]]:
        account_id = self._account_id()
        if settings.SIMULATION_MODE:
            today = date.today().isoformat()
            return [
                {
                    "id": "sim_campaign_001",
                    "account_id": f"act_{account_id}",
                    "name": "Simulated awareness campaign",
                    "objective": "OUTCOME_AWARENESS",
                    "status": "PAUSED",
                    "effective_status": "PAUSED",
                    "daily_budget": "500",
                    "lifetime_budget": None,
                    "currency": settings.META_AD_CURRENCY,
                    "spend": "0",
                    "impressions": "0",
                    "clicks": "0",
                    "actions": [],
                    "date_start": today,
                }
            ]

        await self.get_account()
        campaigns = await self._request_json(
            "GET",
            f"act_{account_id}/campaigns",
            params=self._params(
                {
                    "fields": (
                        "id,account_id,name,objective,status,effective_status,"
                        "daily_budget,lifetime_budget,updated_time"
                    ),
                    "limit": 100,
                }
            ),
        )
        campaign_rows = campaigns.get("data")
        if not isinstance(campaign_rows, list):
            raise MetaAdsError("Meta returned an invalid campaign list")
        result = []
        for campaign in campaign_rows:
            if not isinstance(campaign, dict) or not campaign.get("id"):
                continue
            insights = await self._request_json(
                "GET",
                f"{campaign['id']}/insights",
                params=self._params(
                    {
                        "fields": (
                            "spend,impressions,clicks,actions,date_start,date_stop"
                        ),
                        "date_preset": "today",
                    }
                ),
            )
            insight_rows = insights.get("data", [])
            insight = insight_rows[0] if insight_rows else {}
            result.append(
                {
                    **campaign,
                    "currency": settings.META_AD_CURRENCY,
                    "spend": insight.get("spend", "0"),
                    "impressions": insight.get("impressions", "0"),
                    "clicks": insight.get("clicks", "0"),
                    "actions": insight.get("actions", []),
                    "date_start": insight.get("date_start", date.today().isoformat()),
                }
            )
        return result

    async def get_campaign(self, campaign_id: str) -> Dict[str, Any]:
        if settings.SIMULATION_MODE:
            return {
                "id": campaign_id,
                "daily_budget": "500",
                "lifetime_budget": None,
                "status": "PAUSED",
            }
        payload = await self._request_json(
            "GET",
            campaign_id,
            params=self._params(
                {
                    "fields": (
                        "id,account_id,daily_budget,lifetime_budget,status,"
                        "adsets{id,daily_budget,lifetime_budget,status}"
                    )
                }
            ),
        )
        if str(payload.get("account_id", "")).removeprefix("act_") != self._account_id():
            raise MetaAdsError("Campaign does not belong to the configured Ad Account")
        return payload

    async def update_budget(self, campaign_id: str, budget_minor: int) -> Dict[str, Any]:
        if settings.SIMULATION_MODE:
            return {"id": campaign_id, "daily_budget": str(budget_minor)}
        return await self._request_json(
            "POST",
            campaign_id,
            params=self._params(),
            data={"daily_budget": str(budget_minor)},
        )

    async def update_status(self, campaign_id: str, status: str) -> Dict[str, Any]:
        if settings.SIMULATION_MODE:
            return {"id": campaign_id, "status": status}
        return await self._request_json(
            "POST",
            campaign_id,
            params=self._params(),
            data={"status": status},
        )


meta_ads_client = MetaAdsClient()


def currency_to_minor_units(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise MetaAdsError("Meta returned an invalid monetary value") from exc
    if not amount.is_finite() or amount < 0:
        raise MetaAdsError("Meta returned an invalid monetary value")
    minor_units = amount * 100
    if minor_units != minor_units.to_integral_value():
        raise MetaAdsError("Meta returned a monetary value with invalid precision")
    return int(minor_units)


def parse_meta_budget_minor(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        budget = Decimal(str(value))
    except InvalidOperation as exc:
        raise MetaAdsError("Meta returned an invalid campaign budget") from exc
    if not budget.is_finite() or budget < 0 or budget != budget.to_integral_value():
        raise MetaAdsError("Meta returned an invalid campaign budget")
    return int(budget)
