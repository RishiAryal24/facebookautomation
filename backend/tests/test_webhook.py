import hashlib
import hmac
import json


def _signature(secret, payload):
    digest = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def test_webhook_rejects_missing_or_invalid_signature(client, monkeypatch):
    from app.config import settings

    payload = b'{"object":"page","entry":[]}'
    monkeypatch.setattr(settings, "META_APP_SECRET", "test-meta-app-secret")

    missing = client.post("/api/v1/webhook/", content=payload)
    invalid = client.post(
        "/api/v1/webhook/",
        content=payload,
        headers={"X-Hub-Signature-256": "sha256=invalid"},
    )

    assert missing.status_code == 401
    assert invalid.status_code == 401

    monkeypatch.setattr(settings, "META_APP_SECRET", "")
    unconfigured = client.post(
        "/api/v1/webhook/",
        content=payload,
        headers={"X-Hub-Signature-256": _signature("test-meta-app-secret", payload)},
    )
    assert unconfigured.status_code == 503


def test_webhook_accepts_valid_signature_and_parses_comment_event(client, monkeypatch):
    from app.config import settings
    from app.services.automation_runner import automation_engine

    secret = "test-meta-app-secret"
    payload = json.dumps(
        {
            "object": "page",
            "entry": [
                {
                    "id": "pyloom_page_001",
                    "changes": [
                        {
                            "value": {
                                "item": "comment",
                                "verb": "add",
                                "comment_id": "signed-webhook-comment",
                                "post_id": "signed-webhook-post",
                                "from": {"id": "customer-1", "name": "Test Customer"},
                                "message": "Hello",
                            }
                        }
                    ],
                }
            ],
        }
    ).encode()
    processed = []

    async def process_comment(**kwargs):
        processed.append(kwargs)
        await kwargs["db"].commit()

    monkeypatch.setattr(settings, "META_APP_SECRET", secret)
    monkeypatch.setattr(settings, "SIMULATION_MODE", False)
    monkeypatch.setattr(automation_engine, "process_incoming_comment", process_comment)
    response = client.post(
        "/api/v1/webhook/",
        content=payload,
        headers={"X-Hub-Signature-256": _signature(secret, payload)},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "processed"}
    assert len(processed) == 1
    assert processed[0]["meta_comment_id"] == "signed-webhook-comment"
