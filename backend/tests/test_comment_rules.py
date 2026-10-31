def test_matching_template_rule_creates_review_only_comment(client):
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "phase-two-admin@example.com",
            "password": "A-strong-test-password-123",
        },
    )
    assert login_response.status_code == 200
    client.headers["Authorization"] = f"Bearer {login_response.json()['access_token']}"

    rule_response = client.post(
        "/api/v1/rules/",
        json={
            "page_id": 1,
            "name": "Special test reply",
            "trigger_keyword": "special-test",
            "response_template": "Hello {name}, thanks for asking.",
            "target_language": "en",
        },
    )
    assert rule_response.status_code == 200

    comment_response = client.post(
        "/api/v1/comments/simulate",
        json={
            "page_id": 1,
            "sender_name": "Test Customer",
            "message": "I have a SPECIAL-TEST question.",
        },
    )

    assert comment_response.status_code == 200
    comment = comment_response.json()
    assert comment["status"] == "pending_approval"
    assert comment["is_simulated"] is True
    assert comment["ai_generation_source"] == "automation_rule"
    assert comment["ai_draft_reply"] == "Hello Test Customer, thanks for asking."

    publish_response = client.post(
        f"/api/v1/comments/{comment['id']}/approve",
        json={"edited_reply": "This must never be published."},
    )
    assert publish_response.status_code == 409


def test_simulated_gemini_comment_never_calls_meta_publisher(client, monkeypatch):
    from app.services import automation_runner as runner_module
    from app.services.gemini_service import gemini_service

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "phase-two-admin@example.com",
            "password": "A-strong-test-password-123",
        },
    )
    assert login_response.status_code == 200
    client.headers["Authorization"] = f"Bearer {login_response.json()['access_token']}"
    page_response = client.put(
        "/api/v1/pages/1",
        json={"auto_approve_enabled": True},
    )
    assert page_response.status_code == 200

    async def generate_reply(**kwargs):
        return {
            "detected_language": "en",
            "sentiment": "positive",
            "reply": "Thank you!",
            "confidence": 0.99,
            "source": "gemini_api",
        }

    async def publisher_must_not_run(*args, **kwargs):
        raise AssertionError("Simulation attempted a live Meta publish")

    async def allow_operating_hours(*args, **kwargs):
        return True

    async def allow_rate_limit(*args, **kwargs):
        return True

    monkeypatch.setattr(gemini_service, "generate_comment_reply", generate_reply)
    monkeypatch.setattr(runner_module.meta_client, "publish_comment_reply", publisher_must_not_run)
    monkeypatch.setattr(runner_module.automation_engine, "is_within_operating_hours", allow_operating_hours)
    monkeypatch.setattr(runner_module.automation_engine, "check_rate_limit", allow_rate_limit)

    response = client.post(
        "/api/v1/comments/simulate",
        json={
            "page_id": 1,
            "sender_name": "Test Customer",
            "message": "A positive simulated comment.",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "pending_approval"
    assert response.json()["is_simulated"] is True
