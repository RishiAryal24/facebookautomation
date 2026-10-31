import os


os.environ.update(
    {
        "SECRET_KEY": "phase-two-test-signing-secret-key-at-least-32",
        "ENCRYPTION_KEY": "s2bQpZ7k4n1gE8wL-5rTvX9yUz3mA6cD0eF2hJ4lNo8=",
        "META_VERIFY_TOKEN": "phase-two-test-webhook-token",
        "INITIAL_ADMIN_EMAIL": "phase-two-admin@example.com",
        "INITIAL_ADMIN_PASSWORD": "A-strong-test-password-123",
        "AUTH_COOKIE_SECURE": "false",
        "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "BACKEND_CORS_ORIGINS": '["http://testserver"]',
    }
)

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clear_client_auth(client):
    client.headers.pop("Authorization", None)
    client.cookies.clear()
