def test_protected_routes_reject_anonymous_requests(client):
    assert client.get("/api/v1/pages/").status_code == 401
    assert client.post("/api/v1/reports/emergency-stop").status_code == 401
    assert client.post("/api/v1/auth/register", json={
        "email": "unauthorized@example.com",
        "password": "A-strong-test-password-123",
        "role": "super_admin",
    }).status_code == 401


def test_login_refresh_rotation_and_logout(client):
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "phase-two-admin@example.com",
            "password": "A-strong-test-password-123",
        },
    )
    assert login_response.status_code == 200
    login_data = login_response.json()
    assert login_data["user_role"] == "super_admin"
    assert login_data["expires_in"] == 900
    old_refresh_token = client.cookies.get("refresh_token")
    assert old_refresh_token
    assert "httponly" in login_response.headers["set-cookie"].lower()

    client.headers["Authorization"] = f"Bearer {login_data['access_token']}"
    assert client.get("/api/v1/auth/me").json()["email"] == "phase-two-admin@example.com"

    refresh_response = client.post("/api/v1/auth/refresh")
    assert refresh_response.status_code == 200
    assert refresh_response.json()["access_token"] != login_data["access_token"]
    new_refresh_token = client.cookies.get("refresh_token")
    assert new_refresh_token != old_refresh_token

    client.cookies.clear()
    client.cookies.set("refresh_token", old_refresh_token)
    reused_token_response = client.post("/api/v1/auth/refresh")
    assert reused_token_response.status_code == 401

    client.cookies.set("refresh_token", new_refresh_token)
    assert client.post("/api/v1/auth/logout").status_code == 200
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_viewer_cannot_register_users_or_change_pages(client):
    admin_login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "phase-two-admin@example.com",
            "password": "A-strong-test-password-123",
        },
    )
    assert admin_login.status_code == 200
    client.headers["Authorization"] = f"Bearer {admin_login.json()['access_token']}"

    create_viewer = client.post(
        "/api/v1/auth/register",
        json={
            "email": "phase-two-viewer@example.com",
            "password": "Another-strong-password-123",
            "role": "viewer",
        },
    )
    assert create_viewer.status_code == 201
    assert create_viewer.json()["role"] == "viewer"

    viewer_login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "phase-two-viewer@example.com",
            "password": "Another-strong-password-123",
        },
    )
    assert viewer_login.status_code == 200
    client.headers["Authorization"] = f"Bearer {viewer_login.json()['access_token']}"

    assert client.get("/api/v1/pages/").status_code == 200
    assert client.post("/api/v1/reports/emergency-stop").status_code == 403
    assert client.post(
        "/api/v1/pages/",
        json={"meta_page_id": "test-page", "name": "Test Page"},
    ).status_code == 403
    assert client.post(
        "/api/v1/auth/register",
        json={
            "email": "second-viewer@example.com",
            "password": "Another-strong-password-123",
            "role": "super_admin",
        },
    ).status_code == 403


def test_simulated_page_token_cannot_be_connected_as_a_real_page(client):
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "phase-two-admin@example.com",
            "password": "A-strong-test-password-123",
        },
    )
    client.headers["Authorization"] = f"Bearer {login_response.json()['access_token']}"

    response = client.post(
        "/api/v1/pages/",
        json={
            "meta_page_id": "simulated_page_phase_two",
            "name": "Simulated Test Page",
            "access_token": "mock_test_token",
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"]["status"] == "connection_failed"
    assert "mock_test_token" not in response.text


def test_mock_credentials_are_rejected_when_simulation_is_disabled(client, monkeypatch):
    from app.config import settings

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "phase-two-admin@example.com",
            "password": "A-strong-test-password-123",
        },
    )
    client.headers["Authorization"] = f"Bearer {login_response.json()['access_token']}"
    monkeypatch.setattr(settings, "SIMULATION_MODE", False)

    response = client.post(
        "/api/v1/pages/",
        json={
            "meta_page_id": "123456789",
            "name": "Live Test Page",
            "access_token": "mock_invalid_token",
        },
    )
    assert response.status_code == 422
    assert "valid Page access token" in response.json()["detail"]["message"]
