import hashlib
import hmac
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

import httpx
from cryptography.fernet import InvalidToken

from app.config import settings
from app.core.security import decrypt_token

logger = logging.getLogger(__name__)


class MetaAPIError(RuntimeError):
    """A safe, user-facing Meta API failure without credential values."""

    def __init__(
        self,
        message: str,
        *,
        http_status: Optional[int] = None,
        meta_error: Optional[Dict[str, Any]] = None,
        published_post_id: Optional[str] = None,
        publication_uncertain: bool = False,
    ):
        super().__init__(message)
        self.http_status = http_status
        self.meta_error = meta_error
        self.published_post_id = published_post_id
        self.publication_uncertain = publication_uncertain


class MetaGraphClient:
    REQUIRED_PAGE_PERMISSIONS = {
        "pages_read_engagement",
        "pages_manage_posts",
    }
    REQUIRED_PAGE_TASKS = {"CREATE_CONTENT"}

    def __init__(self):
        self.base_url = f"https://graph.facebook.com/{settings.META_GRAPH_API_VERSION}"
        self.app_id = settings.META_APP_ID
        self.app_secret = settings.META_APP_SECRET

    def get_page_access_token(
        self,
        page: Any,
        *,
        allow_revalidation: bool = False,
    ) -> str:
        if not page.is_connected or not page.access_token_enc:
            raise MetaAPIError("The Facebook Page has no connected access token")
        try:
            access_token = decrypt_token(page.access_token_enc)
        except (InvalidToken, UnicodeDecodeError, ValueError) as exc:
            raise MetaAPIError("The stored Page access token could not be decrypted") from exc
        if access_token.startswith("mock_"):
            if settings.SIMULATION_MODE and page.token_status == "simulated":
                return access_token
            raise MetaAPIError("A simulated Page token cannot be used for live Meta operations")
        if not allow_revalidation and page.token_status not in {"valid", "expiring_soon"}:
            raise MetaAPIError("The Facebook Page requires token reauthorization")
        if not allow_revalidation and (
            not page.meta_app_id or page.meta_app_id != self.app_id
        ):
            raise MetaAPIError("The stored Page token must be revalidated for the configured Meta app")
        return access_token

    @staticmethod
    def validation_failure_status(error: MetaAPIError) -> str:
        meta_error = error.meta_error or {}
        if meta_error.get("code") == 190:
            return "reauthorization_required"
        if meta_error.get("code") in {10, 200, 201, 202}:
            return "permission_missing"
        return "connection_failed"

    def _require_live_token(self, access_token: str) -> None:
        if not access_token or access_token.startswith("mock_"):
            raise MetaAPIError("A valid Page access token is required outside simulation mode")

    def _authenticated_params(
        self,
        params: Optional[Dict[str, Any]],
        access_token: str,
    ) -> Dict[str, Any]:
        self._require_live_token(access_token)
        result = dict(params or {})
        result["access_token"] = access_token
        if self.app_secret:
            result["appsecret_proof"] = hmac.new(
                self.app_secret.encode(),
                access_token.encode(),
                hashlib.sha256,
            ).hexdigest()
        return result

    async def diagnose_page_authentication(
        self,
        page_id: str,
        access_token: str,
        user_access_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        self._require_live_token(access_token)
        if not re.fullmatch(r"\d+", page_id):
            raise MetaAPIError("Meta Page ID must contain only digits")

        async def probe(
            url: str,
            params: Dict[str, Any],
            fields: tuple[str, ...],
            *,
            page_match_id: Optional[str] = None,
        ) -> Dict[str, Any]:
            try:
                payload = await self._request_json("GET", url, params=params)
            except MetaAPIError as err:
                return {
                    "success": False,
                    "http_status": err.http_status,
                    "meta_error": err.meta_error or {},
                }

            data = payload.get("data", payload)
            if isinstance(data, list):
                items = [
                    {
                        field: item[field]
                        for field in fields
                        if isinstance(item, dict) and field in item
                    }
                    for item in data
                    if isinstance(item, dict)
                    and (
                        page_match_id is None
                        or str(item.get("id")) == page_match_id
                    )
                ]
                return {
                    "success": True,
                    "http_status": 200,
                    "result": {
                        "items": items,
                        "page_match_found": bool(items) if page_match_id else None,
                    },
                }
            if not isinstance(data, dict):
                data = {}
            return {
                "success": True,
                "http_status": 200,
                "result": {
                    field: data[field]
                    for field in fields
                    if field in data
                },
            }

        page_url = f"{self.base_url}/{page_id}"
        page_fields = ("id", "name", "category", "picture")
        page_params = {"fields": ",".join(page_fields), "access_token": access_token}
        page_without_proof = await probe(
            page_url,
            page_params,
            page_fields,
        )
        page_with_proof = await probe(
            page_url,
            self._authenticated_params({"fields": ",".join(page_fields)}, access_token),
            page_fields,
        )
        if user_access_token:
            page_tasks = await probe(
                f"{self.base_url}/me/accounts",
                self._authenticated_params({"fields": "id,tasks"}, user_access_token),
                ("id", "tasks"),
                page_match_id=page_id,
            )
            user_debug_token = await probe(
                f"{self.base_url}/debug_token",
                {
                    "input_token": user_access_token,
                    "access_token": f"{self.app_id}|{self.app_secret}",
                },
                (
                    "app_id",
                    "type",
                    "is_valid",
                    "expires_at",
                    "scopes",
                ),
            )
        else:
            page_tasks = {
                "success": False,
                "http_status": None,
                "meta_error": {
                    "message": "A temporary User Access Token is required to verify Page tasks."
                },
            }
            user_debug_token = page_tasks

        if not self.app_id or not self.app_secret:
            missing = {
                "success": False,
                "http_status": None,
                "meta_error": {
                    "message": "META_APP_ID and META_APP_SECRET must be configured"
                },
            }
            return {
                "submitted_token_used_unchanged": True,
                "checks": {
                    "page_read_without_appsecret_proof": page_without_proof,
                    "page_read_with_appsecret_proof": page_with_proof,
                    "page_tasks_via_accounts_edge": page_tasks,
                    "user_token_debug_token": user_debug_token,
                    "app_identity": missing,
                    "debug_token": missing,
                },
            }

        app_access_token = f"{self.app_id}|{self.app_secret}"
        app_identity = await probe(
            f"{self.base_url}/{self.app_id}",
            {"fields": "id,name", "access_token": app_access_token},
            ("id", "name"),
        )
        debug_token = await probe(
            f"{self.base_url}/debug_token",
            {
                "input_token": access_token,
                "access_token": app_access_token,
            },
            (
                "app_id",
                "type",
                "is_valid",
                "expires_at",
                "data_access_expires_at",
                "scopes",
            ),
        )
        return {
            "submitted_token_used_unchanged": True,
            "checks": {
                "page_read_without_appsecret_proof": page_without_proof,
                "page_read_with_appsecret_proof": page_with_proof,
                "page_tasks_via_accounts_edge": page_tasks,
                "user_token_debug_token": user_debug_token,
                "app_identity": app_identity,
                "debug_token": debug_token,
            },
        }

    async def _request_json(
        self,
        method: str,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        timeout: float = 15.0,
    ) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(method, url, params=params, data=data)
        except httpx.TimeoutException as exc:
            logger.warning(
                "Meta Graph API request timed out",
                extra={"meta_method": method, "meta_path": urlsplit(url).path},
            )
            raise MetaAPIError("Meta Graph API request timed out") from exc
        except httpx.HTTPError as exc:
            logger.warning(
                "Meta Graph API request failed before receiving a response",
                extra={"meta_method": method, "meta_path": urlsplit(url).path},
            )
            raise MetaAPIError("Meta Graph API request failed") from exc

        try:
            payload = response.json()
        except ValueError:
            payload = {}

        meta_error = payload.get("error") if isinstance(payload, dict) else None
        if not response.is_success or meta_error:
            error_code = meta_error.get("code") if isinstance(meta_error, dict) else None
            safe_error = (
                {
                    key: meta_error[key]
                    for key in ("message", "type", "code", "error_subcode", "fbtrace_id")
                    if key in meta_error
                }
                if isinstance(meta_error, dict)
                else {}
            )
            credential_values = {
                str(value)
                for source in (params, data)
                if source
                for key, value in source.items()
                if value and any(secret_word in key.lower() for secret_word in ("token", "secret", "proof"))
            }
            credential_values.update(
                secret
                for secret in (self.app_secret, settings.META_APP_SECRET)
                if secret
            )
            if isinstance(safe_error.get("message"), str):
                for credential in credential_values:
                    safe_error["message"] = safe_error["message"].replace(
                        credential,
                        "[redacted]",
                    )
            logger.warning(
                "Meta Graph API request returned an error: method=%s path=%s "
                "HTTP %s response=%s",
                method,
                urlsplit(url).path,
                response.status_code,
                json.dumps(safe_error, sort_keys=True),
            )
            suffix = f" (Meta error {error_code})" if error_code else ""
            raise MetaAPIError(
                f"Meta Graph API request failed with HTTP {response.status_code}{suffix}",
                http_status=response.status_code,
                meta_error=safe_error,
            )
        if not isinstance(payload, dict):
            raise MetaAPIError("Meta Graph API returned an invalid response")
        safe_response = {
            key: payload[key]
            for key in ("id", "is_published", "permalink_url")
            if key in payload
        }
        logger.info(
            "Meta Graph API request succeeded: method=%s path=%s HTTP %s response=%s",
            method,
            urlsplit(url).path,
            response.status_code,
            json.dumps(safe_response, sort_keys=True),
        )
        return payload

    async def validate_page_credentials(
        self,
        page_id: str,
        access_token: str,
        *,
        user_access_token: Optional[str] = None,
        force_live: bool = False,
    ) -> Dict[str, Any]:
        if settings.SIMULATION_MODE and not force_live:
            return {
                "status": "simulated",
                "expires_at": None,
                "permissions": ["simulation"],
                "tasks": [],
                "page": await self.get_page_info(page_id, access_token),
            }

        self._require_live_token(access_token)
        if not re.fullmatch(r"\d+", page_id):
            raise MetaAPIError("Meta Page ID must contain only digits")
        if not self.app_id or not self.app_secret:
            raise MetaAPIError("META_APP_ID and META_APP_SECRET must be configured")

        debug_response = await self._request_json(
            "GET",
            f"{self.base_url}/debug_token",
            params={
                "input_token": access_token,
                "access_token": f"{self.app_id}|{self.app_secret}",
            },
        )
        token_info = debug_response.get("data", {})
        if not isinstance(token_info, dict):
            raise MetaAPIError("Meta returned an invalid token validation response")
        returned_app_id = str(token_info.get("app_id", ""))
        if returned_app_id != self.app_id:
            raise MetaAPIError(
                "The Page access token was issued for a different Meta app",
                meta_error={"message": "Meta app ID mismatch"},
            )
        if not token_info.get("is_valid"):
            raise MetaAPIError(
                "Meta rejected the Page access token",
                meta_error={"message": "Meta reports that this access token is invalid", "code": 190},
            )
        token_type = token_info.get("type")
        if str(token_type).upper() != "PAGE":
            raise MetaAPIError(
                "A Page access token is required; the submitted token is not a Page token",
                meta_error={"message": "Meta token type is not PAGE"},
            )
        expires_timestamp = token_info.get("expires_at")
        if expires_timestamp and float(expires_timestamp) <= datetime.now(timezone.utc).timestamp():
            raise MetaAPIError(
                "The Page access token has expired and must be replaced",
                meta_error={
                    "message": "Meta reports that this access token has expired",
                    "code": 190,
                    "error_subcode": 463,
                },
            )

        permissions = set(token_info.get("scopes", []))
        missing_permissions = self.REQUIRED_PAGE_PERMISSIONS - permissions
        if missing_permissions:
            missing = ", ".join(sorted(missing_permissions))
            raise MetaAPIError(
                f"Page token is missing required permissions: {missing}",
                meta_error={"message": f"Missing required permissions: {missing}", "code": 10},
            )

        page_info = await self.get_page_info(
            page_id,
            access_token,
            force_live=True,
        )
        if str(page_info.get("id")) != page_id:
            raise MetaAPIError("The provided token does not grant access to this Page")
        page_tasks: Optional[set[str]] = None
        if user_access_token:
            self._require_live_token(user_access_token)
            user_debug_response = await self._request_json(
                "GET",
                f"{self.base_url}/debug_token",
                params={
                    "input_token": user_access_token,
                    "access_token": f"{self.app_id}|{self.app_secret}",
                },
            )
            user_token_info = user_debug_response.get("data", {})
            if not isinstance(user_token_info, dict):
                raise MetaAPIError("Meta returned an invalid User token validation response")
            if str(user_token_info.get("app_id", "")) != self.app_id:
                raise MetaAPIError(
                    "The User access token was issued for a different Meta app",
                    meta_error={"message": "Meta app ID mismatch"},
                )
            if not user_token_info.get("is_valid"):
                raise MetaAPIError(
                    "Meta rejected the temporary User access token",
                    meta_error={
                        "message": "Meta reports that the User access token is invalid",
                        "code": 190,
                    },
                )
            if str(user_token_info.get("type", "")).upper() != "USER":
                raise MetaAPIError(
                    "A User access token is required to verify Page tasks",
                    meta_error={"message": "Meta token type is not USER"},
                )
            user_permissions = set(user_token_info.get("scopes", []))
            if "pages_show_list" not in user_permissions:
                raise MetaAPIError(
                    "The temporary User token is missing pages_show_list, required to verify Page tasks",
                    meta_error={
                        "message": "Missing required User permission: pages_show_list",
                        "code": 10,
                    },
                )
            page_tasks = set(
                await self.get_page_tasks(
                    page_id,
                    user_access_token,
                    force_live=True,
                )
            )
            missing_tasks = self.REQUIRED_PAGE_TASKS - page_tasks
            if missing_tasks:
                missing = ", ".join(sorted(missing_tasks))
                raise MetaAPIError(
                    f"Page is missing required Page access tasks: {missing}",
                    meta_error={"message": f"Missing required Page tasks: {missing}", "code": 10},
                )

        data_access_expires_timestamp = token_info.get("data_access_expires_at")
        if not expires_timestamp and data_access_expires_timestamp:
            expires_timestamp = data_access_expires_timestamp
        expires_at = (
            datetime.fromtimestamp(expires_timestamp, tz=timezone.utc)
            if expires_timestamp
            else None
        )
        return {
            "status": "valid",
            "expires_at": expires_at,
            "permissions": sorted(permissions),
            "tasks": sorted(page_tasks) if page_tasks is not None else None,
            "meta_app_id": returned_app_id,
            "page": page_info,
        }

    async def get_page_tasks(
        self,
        page_id: str,
        access_token: str,
        *,
        force_live: bool = False,
    ) -> List[str]:
        if settings.SIMULATION_MODE and not force_live:
            return []
        params = self._authenticated_params({"fields": "id,tasks"}, access_token)
        response = await self._request_json(
            "GET",
            f"{self.base_url}/me/accounts",
            params=params,
        )
        pages = response.get("data", [])
        if not isinstance(pages, list):
            raise MetaAPIError("Meta returned an invalid Page task response")
        for page in pages:
            if isinstance(page, dict) and str(page.get("id")) == page_id:
                tasks = page.get("tasks", [])
                if isinstance(tasks, list):
                    return [str(task) for task in tasks]
                raise MetaAPIError("Meta returned invalid Page tasks")
        return []

    async def get_page_info(
        self,
        page_id: str,
        access_token: str,
        *,
        force_live: bool = False,
    ) -> Dict[str, Any]:
        if settings.SIMULATION_MODE and not force_live:
            return {
                "id": page_id,
                "name": "PyLoom Official Store (Simulated)",
                "category": "E-Commerce & Retail",
                "picture": {
                    "data": {
                        "url": "https://images.unsplash.com/photo-1522071820081-009f0129c71c?w=128&q=80"
                    }
                },
            }

        params = self._authenticated_params(
            {"fields": "id,name,category,picture.type(large)"},
            access_token,
        )
        return await self._request_json("GET", f"{self.base_url}/{page_id}", params=params)

    async def fetch_page_posts(
        self,
        page_id: str,
        access_token: str,
        limit: int = 10,
        *,
        force_live: bool = False,
    ) -> List[Dict[str, Any]]:
        if settings.SIMULATION_MODE and not force_live:
            return [
                {
                    "id": f"{page_id}_post_101",
                    "message": "Big Festival Sale is LIVE! Enjoy up to 40% OFF on all items.",
                    "permalink_url": "https://facebook.com/posts/101",
                    "full_picture": "https://images.unsplash.com/photo-1607082348824-0a96f2a4b9da?w=600&q=80",
                    "created_time": datetime.now(timezone.utc).isoformat(),
                    "likes": {"summary": {"total_count": 84}},
                    "comments": {"summary": {"total_count": 12}},
                },
                {
                    "id": f"{page_id}_post_102",
                    "message": "नयाँ सामानहरू आइपुगेका छन्! नेपालभर होम डेलिभरी उपलब्ध छ।",
                    "permalink_url": "https://facebook.com/posts/102",
                    "full_picture": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&q=80",
                    "created_time": datetime.now(timezone.utc).isoformat(),
                    "likes": {"summary": {"total_count": 142}},
                    "comments": {"summary": {"total_count": 27}},
                },
            ]

        params = self._authenticated_params(
            {
                "fields": (
                    "id,message,permalink_url,full_picture,created_time,"
                    "likes.summary(true),comments.summary(true)"
                ),
                "limit": limit,
            },
            access_token,
        )
        payload = await self._request_json(
            "GET",
            f"{self.base_url}/{page_id}/feed",
            params=params,
        )
        return payload.get("data", [])

    async def fetch_post_comments(
        self,
        post_id: str,
        access_token: str,
        limit: int = 25,
    ) -> List[Dict[str, Any]]:
        if settings.SIMULATION_MODE:
            return []

        params = self._authenticated_params(
            {
                "fields": "id,from,message,created_time,like_count",
                "limit": limit,
            },
            access_token,
        )
        payload = await self._request_json(
            "GET",
            f"{self.base_url}/{post_id}/comments",
            params=params,
        )
        return payload.get("data", [])

    async def publish_comment_reply(
        self,
        parent_comment_id: str,
        message: str,
        access_token: str,
    ) -> Dict[str, Any]:
        if settings.SIMULATION_MODE:
            raise MetaAPIError(
                "Live Facebook comment replies are disabled while SIMULATION_MODE is enabled"
            )

        data = self._authenticated_params({"message": message}, access_token)
        return await self._request_json(
            "POST",
            f"{self.base_url}/{parent_comment_id}/comments",
            data=data,
        )

    async def like_comment(self, comment_id: str, access_token: str) -> Dict[str, Any]:
        if settings.SIMULATION_MODE:
            raise MetaAPIError(
                "Live Facebook comment likes are disabled while SIMULATION_MODE is enabled"
            )

        data = self._authenticated_params({}, access_token)
        return await self._request_json(
            "POST",
            f"{self.base_url}/{comment_id}/likes",
            data=data,
        )

    async def create_page_post(
        self,
        page_id: str,
        message: str,
        access_token: str,
        media_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        if settings.SIMULATION_MODE:
            raise MetaAPIError(
                "Live Facebook publishing is disabled while SIMULATION_MODE is enabled"
            )

        data: Dict[str, Any] = {"message": message, "published": True}
        if media_url:
            data["link"] = media_url
        data = self._authenticated_params(data, access_token)
        publish_response = await self._request_json(
            "POST",
            f"{self.base_url}/{page_id}/feed",
            data=data,
            timeout=20.0,
        )
        post_id = publish_response.get("id")
        if not isinstance(post_id, str) or not post_id:
            raise MetaAPIError(
                "Meta accepted the publish request but returned no post ID; publication is unverified",
                publication_uncertain=True,
            )

        try:
            verified_post = await self._request_json(
                "GET",
                f"{self.base_url}/{post_id}",
                params=self._authenticated_params(
                    {"fields": "id,is_published,permalink_url"},
                    access_token,
                ),
            )
        except MetaAPIError as exc:
            raise MetaAPIError(
                f"Meta returned post ID {post_id}, but the post could not be verified",
                http_status=exc.http_status,
                meta_error=exc.meta_error,
                published_post_id=post_id,
                publication_uncertain=True,
            ) from exc

        if (
            verified_post.get("id") != post_id
            or verified_post.get("is_published") is not True
        ):
            raise MetaAPIError(
                f"Meta returned post ID {post_id}, but did not confirm it is published",
                published_post_id=post_id,
                publication_uncertain=True,
            )

        logger.info(
            "Meta Page post publication verified: page_id=%s post_id=%s",
            page_id,
            post_id,
        )
        return {
            "id": post_id,
            "permalink_url": verified_post.get("permalink_url"),
            "verified": True,
        }


meta_client = MetaGraphClient()
