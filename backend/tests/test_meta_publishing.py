import asyncio
import hashlib
import hmac
import logging

import httpx
import pytest


class MockAsyncClient:
    def __init__(self, responses, requests, **kwargs):
        self.responses = responses
        self.requests = requests

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return False

    async def request(self, method, url, *, params=None, data=None):
        self.requests.append(
            {"method": method, "url": url, "params": params, "data": data}
        )
        return self.responses.pop(0)


def _response(status_code, payload):
    return httpx.Response(status_code, json=payload)


def test_page_post_sends_authenticated_published_request_and_verifies_post(
    monkeypatch,
    caplog,
):
    from app.config import settings
    from app.services import meta_client as meta_client_module
    from app.services.meta_client import MetaGraphClient

    token = "synthetic-page-token-for-test"
    requests = []
    responses = [
        _response(200, {"id": "123456789_987654321"}),
        _response(
            200,
            {
                "id": "123456789_987654321",
                "is_published": True,
                "permalink_url": "https://facebook.com/123456789/posts/987654321",
            },
        ),
    ]

    monkeypatch.setattr(settings, "SIMULATION_MODE", False)
    monkeypatch.setattr(
        meta_client_module.httpx,
        "AsyncClient",
        lambda **kwargs: MockAsyncClient(responses, requests, **kwargs),
    )
    client = MetaGraphClient()
    client.app_secret = ""

    async def publish():
        return await client.create_page_post(
            page_id="123456789",
            message="Reviewed test message",
            access_token=token,
        )

    with caplog.at_level(logging.INFO, logger="app.services.meta_client"):
        result = asyncio.run(publish())

    assert result == {
        "id": "123456789_987654321",
        "permalink_url": "https://facebook.com/123456789/posts/987654321",
        "verified": True,
    }
    assert requests[0]["method"] == "POST"
    assert requests[0]["url"].endswith("/123456789/feed")
    assert requests[0]["data"]["message"] == "Reviewed test message"
    assert requests[0]["data"]["published"] is True
    assert requests[0]["data"]["access_token"] == token
    assert requests[1]["method"] == "GET"
    assert requests[1]["url"].endswith("/123456789_987654321")
    assert requests[1]["params"]["fields"] == "id,is_published,permalink_url"
    assert requests[1]["params"]["access_token"] == token
    assert "123456789_987654321" in caplog.text
    assert token not in caplog.text


def test_simulation_mode_cannot_return_a_success_shaped_publish_result(monkeypatch):
    from app.config import settings
    from app.services.meta_client import MetaAPIError, MetaGraphClient

    monkeypatch.setattr(settings, "SIMULATION_MODE", True)

    async def publish():
        return await MetaGraphClient().create_page_post(
            page_id="123456789",
            message="Should not be posted",
            access_token="mock_test_token",
        )

    with pytest.raises(MetaAPIError, match="SIMULATION_MODE"):
        asyncio.run(publish())


def test_live_page_validation_requires_read_and_publish_permissions(monkeypatch):
    from app.config import settings
    from app.services.meta_client import MetaAPIError, MetaGraphClient

    monkeypatch.setattr(settings, "SIMULATION_MODE", False)
    client = MetaGraphClient()
    client.app_id = "test-app-id"
    client.app_secret = "test-app-secret"

    async def debug_token(*args, **kwargs):
        return {
            "data": {
                "app_id": "test-app-id",
                "type": "PAGE",
                "is_valid": True,
                "scopes": ["pages_manage_posts"],
            }
        }

    client._request_json = debug_token

    async def validate():
        return await client.validate_page_credentials(
            "123456789",
            "synthetic-page-token-for-test",
        )

    with pytest.raises(MetaAPIError, match="pages_read_engagement"):
        asyncio.run(validate())


def test_live_page_validation_requires_create_content_page_task(monkeypatch):
    from app.config import settings
    from app.services.meta_client import MetaAPIError, MetaGraphClient

    monkeypatch.setattr(settings, "SIMULATION_MODE", False)
    client = MetaGraphClient()
    client.app_id = "test-app-id"
    client.app_secret = "test-app-secret"
    responses = [
        {
            "data": {
                "app_id": "test-app-id",
                "type": "PAGE",
                "is_valid": True,
                "scopes": ["pages_manage_posts", "pages_read_engagement"],
            }
        },
        {"id": "123456789", "name": "Test Page"},
        {
            "data": {
                "app_id": "test-app-id",
                "type": "USER",
                "is_valid": True,
                "scopes": ["pages_show_list"],
            }
        },
        {"data": [{"id": "123456789", "tasks": ["ANALYZE"]}]},
    ]

    async def request_json(*args, **kwargs):
        return responses.pop(0)

    client._request_json = request_json

    async def validate():
        return await client.validate_page_credentials(
            "123456789",
            "synthetic-page-token-for-test",
            user_access_token="synthetic-user-token-for-test",
        )

    with pytest.raises(MetaAPIError, match="CREATE_CONTENT"):
        asyncio.run(validate())


def test_page_validation_uses_configured_app_credentials_and_appsecret_proof(monkeypatch):
    from app.config import settings
    from app.services.meta_client import MetaGraphClient

    token = "synthetic-page-token-for-test"
    user_token = "synthetic-user-token-for-test"
    app_id = "test-meta-app-id"
    app_secret = "test-meta-app-secret"
    requests = []
    responses = [
        {
            "data": {
                "app_id": "test-meta-app-id",
                "type": "PAGE",
                "is_valid": True,
                "scopes": ["pages_manage_posts", "pages_read_engagement"],
            }
        },
        {
            "id": "123456789",
            "name": "Test Page",
        },
        {
            "data": {
                "app_id": app_id,
                "type": "USER",
                "is_valid": True,
                "scopes": ["pages_show_list"],
            }
        },
        {"data": [{"id": "123456789", "tasks": ["CREATE_CONTENT"]}]},
    ]
    monkeypatch.setattr(settings, "SIMULATION_MODE", False)
    client = MetaGraphClient()
    client.app_id = app_id
    client.app_secret = app_secret

    async def request_json(method, url, *, params=None, data=None, timeout=15.0):
        requests.append({"method": method, "params": params, "data": data})
        return responses.pop(0)

    client._request_json = request_json

    async def validate():
        return await client.validate_page_credentials(
            "123456789",
            token,
            user_access_token=user_token,
        )

    result = asyncio.run(validate())

    expected_proof = hmac.new(
        app_secret.encode(),
        token.encode(),
        hashlib.sha256,
    ).hexdigest()
    assert result["status"] == "valid"
    assert requests[0]["params"]["input_token"] == token
    assert requests[0]["params"]["access_token"] == f"{app_id}|{app_secret}"
    assert requests[1]["params"]["access_token"] == token
    assert requests[1]["params"]["appsecret_proof"] == expected_proof
    assert requests[2]["params"]["input_token"] == user_token
    assert requests[3]["params"]["fields"] == "id,tasks"
    assert requests[3]["params"]["access_token"] == user_token
    assert requests[3]["params"]["appsecret_proof"] == hmac.new(
        app_secret.encode(),
        user_token.encode(),
        hashlib.sha256,
    ).hexdigest()


def test_read_only_authentication_diagnostic_compares_page_proof_and_app_token(
    monkeypatch,
    caplog,
):
    from app.config import settings
    from app.services.meta_client import MetaGraphClient

    token = "synthetic-diagnostic-page-token"
    user_token = "synthetic-diagnostic-user-token"
    secret = "synthetic-diagnostic-app-secret"
    app_id = "test-diagnostic-app-id"
    requests = []
    responses = [
        _response(
            400,
            {
                "error": {
                    "message": "Page read rejected",
                    "type": "OAuthException",
                    "code": 190,
                }
            },
        ),
        _response(
            200,
            {"id": "123456789", "name": "Test Page", "category": "Business Page"},
        ),
        _response(
            200,
            {"data": [{"id": "123456789", "tasks": ["CREATE_CONTENT"]}]},
        ),
        _response(
            200,
            {
                "data": {
                    "app_id": app_id,
                    "type": "USER",
                    "is_valid": True,
                    "scopes": ["pages_show_list"],
                }
            },
        ),
        _response(
            200,
            {"id": app_id, "name": "Test App"},
        ),
        _response(
            400,
            {
                "error": {
                    "message": f"Invalid {token} {secret}",
                    "type": "OAuthException",
                    "code": 190,
                }
            },
        ),
    ]
    monkeypatch.setattr(
        settings,
        "SIMULATION_MODE",
        True,
    )
    from app.services import meta_client as meta_client_module

    monkeypatch.setattr(
        meta_client_module.httpx,
        "AsyncClient",
        lambda **kwargs: MockAsyncClient(responses, requests, **kwargs),
    )
    client = MetaGraphClient()
    client.app_id = app_id
    client.app_secret = secret

    result = asyncio.run(
        client.diagnose_page_authentication("123456789", token, user_token)
    )
    expected_proof = hmac.new(
        secret.encode(),
        token.encode(),
        hashlib.sha256,
    ).hexdigest()

    assert result["submitted_token_used_unchanged"] is True
    checks = result["checks"]
    assert checks["page_read_without_appsecret_proof"]["http_status"] == 400
    assert checks["page_read_without_appsecret_proof"]["meta_error"]["code"] == 190
    assert checks["page_read_with_appsecret_proof"]["success"] is True
    assert checks["page_read_with_appsecret_proof"]["result"]["id"] == "123456789"
    assert checks["page_tasks_via_accounts_edge"]["result"]["items"] == [
        {"id": "123456789", "tasks": ["CREATE_CONTENT"]}
    ]
    assert checks["user_token_debug_token"]["result"]["type"] == "USER"
    assert checks["app_identity"]["result"] == {"id": app_id, "name": "Test App"}
    assert checks["debug_token"]["meta_error"]["code"] == 190
    assert len(requests) == 6
    assert requests[0]["params"]["access_token"] == token
    assert "appsecret_proof" not in requests[0]["params"]
    assert requests[1]["params"]["access_token"] == token
    assert requests[1]["params"]["appsecret_proof"] == expected_proof
    assert requests[2]["url"].endswith("/me/accounts")
    assert requests[2]["params"]["access_token"] == user_token
    assert requests[2]["params"]["appsecret_proof"] == hmac.new(
        secret.encode(),
        user_token.encode(),
        hashlib.sha256,
    ).hexdigest()
    assert requests[3]["params"]["input_token"] == user_token
    assert requests[4]["params"]["access_token"] == f"{app_id}|{secret}"
    assert requests[5]["params"]["input_token"] == token
    assert token not in caplog.text
    assert user_token not in caplog.text
    assert secret not in caplog.text
    assert token not in str(result)
    assert user_token not in str(result)
    assert secret not in str(result)


@pytest.mark.parametrize(
    ("debug_data", "page_response", "expected_error"),
    [
        (
            {"app_id": "test-app-id", "type": "PAGE", "is_valid": False, "scopes": []},
            None,
            "Meta rejected the Page access token",
        ),
        (
            {
                "app_id": "test-app-id",
                "type": "PAGE",
                "is_valid": True,
                "expires_at": 1,
                "scopes": ["pages_manage_posts", "pages_read_engagement"],
            },
            None,
            "has expired",
        ),
        (
            {"app_id": "another-app", "type": "PAGE", "is_valid": True, "scopes": []},
            None,
            "different Meta app",
        ),
        (
            {
                "app_id": "test-app-id",
                "type": "USER",
                "is_valid": True,
                "scopes": ["pages_manage_posts", "pages_read_engagement"],
            },
            None,
            "not a Page token",
        ),
        (
            {
                "app_id": "test-app-id",
                "type": "PAGE",
                "is_valid": True,
                "scopes": ["pages_manage_posts", "pages_read_engagement"],
            },
            {"id": "different-page", "name": "Wrong Page", "tasks": ["CREATE_CONTENT"]},
            "does not grant access",
        ),
    ],
)
def test_page_token_validation_rejects_invalid_app_type_and_page(
    monkeypatch,
    debug_data,
    page_response,
    expected_error,
):
    from app.config import settings
    from app.services.meta_client import MetaAPIError, MetaGraphClient

    monkeypatch.setattr(settings, "SIMULATION_MODE", False)
    client = MetaGraphClient()
    client.app_id = "test-app-id"
    client.app_secret = "test-app-secret"
    responses = [{"data": debug_data}]
    if page_response is not None:
        responses.append(page_response)

    async def request_json(*args, **kwargs):
        return responses.pop(0)

    client._request_json = request_json

    async def validate():
        return await client.validate_page_credentials(
            "123456789",
            "synthetic-page-token-for-test",
        )

    with pytest.raises(MetaAPIError, match=expected_error):
        asyncio.run(validate())


def test_meta_http_error_records_safe_details_without_token(monkeypatch, caplog):
    from app.config import settings
    from app.services import meta_client as meta_client_module
    from app.services.meta_client import MetaAPIError, MetaGraphClient

    token = "synthetic-page-token-for-test"
    requests = []
    responses = [
        _response(
            403,
            {
                "error": {
                    "message": f"Rejected {token}",
                    "type": "OAuthException",
                    "code": 200,
                    "error_subcode": 10,
                    "fbtrace_id": "test-trace-id",
                }
            },
        )
    ]
    monkeypatch.setattr(settings, "SIMULATION_MODE", False)
    monkeypatch.setattr(
        meta_client_module.httpx,
        "AsyncClient",
        lambda **kwargs: MockAsyncClient(responses, requests, **kwargs),
    )
    client = MetaGraphClient()
    client.app_secret = ""

    async def publish():
        return await client.create_page_post(
            page_id="123456789",
            message="Reviewed test message",
            access_token=token,
        )

    with caplog.at_level(logging.WARNING, logger="app.services.meta_client"):
        with pytest.raises(MetaAPIError, match="HTTP 403") as exc_info:
            asyncio.run(publish())

    assert exc_info.value.http_status == 403
    assert exc_info.value.meta_error["code"] == 200
    assert exc_info.value.meta_error["fbtrace_id"] == "test-trace-id"
    assert "test-trace-id" in caplog.text
    assert token not in caplog.text


def test_meta_error_logs_redact_debug_token_and_app_secret(monkeypatch, caplog):
    from app.services import meta_client as meta_client_module
    from app.services.meta_client import MetaAPIError, MetaGraphClient

    token = "synthetic-debug-input-token"
    secret = "synthetic-test-app-secret"
    requests = []
    responses = [
        _response(
            400,
            {
                "error": {
                    "message": f"Rejected {token} and {secret}",
                    "type": "OAuthException",
                    "code": 190,
                }
            },
        )
    ]
    monkeypatch.setattr(
        meta_client_module.httpx,
        "AsyncClient",
        lambda **kwargs: MockAsyncClient(responses, requests, **kwargs),
    )
    client = MetaGraphClient()
    client.app_secret = secret

    async def request():
        return await client._request_json(
            "GET",
            "https://graph.facebook.com/v26.0/debug_token",
            params={
                "input_token": token,
                "access_token": f"{client.app_id}|{secret}",
            },
        )

    with caplog.at_level(logging.WARNING, logger="app.services.meta_client"):
        with pytest.raises(MetaAPIError):
            asyncio.run(request())

    assert token not in caplog.text
    assert secret not in caplog.text


def test_post_id_is_not_confirmed_if_meta_does_not_verify_publication(monkeypatch):
    from app.config import settings
    from app.services import meta_client as meta_client_module
    from app.services.meta_client import MetaAPIError, MetaGraphClient

    requests = []
    responses = [
        _response(200, {"id": "123456789_987654321"}),
        _response(
            200,
            {"id": "123456789_987654321", "is_published": False},
        ),
    ]
    monkeypatch.setattr(settings, "SIMULATION_MODE", False)
    monkeypatch.setattr(
        meta_client_module.httpx,
        "AsyncClient",
        lambda **kwargs: MockAsyncClient(responses, requests, **kwargs),
    )
    client = MetaGraphClient()
    client.app_secret = ""

    async def publish():
        return await client.create_page_post(
            page_id="123456789",
            message="Reviewed test message",
            access_token="synthetic-page-token-for-test",
        )

    with pytest.raises(MetaAPIError, match="did not confirm") as exc_info:
        asyncio.run(publish())

    assert exc_info.value.publication_uncertain is True
    assert exc_info.value.published_post_id == "123456789_987654321"
