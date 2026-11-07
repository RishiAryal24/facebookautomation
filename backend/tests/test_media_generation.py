import asyncio
import base64
from types import SimpleNamespace

import pytest

from app.config import settings
from app.services.media_generation import (
    GEMINI_IMAGE_REQUEST_TIMEOUT_MS,
    MediaGenerationError,
    MediaGenerationService,
)


def test_generated_image_is_saved_as_real_local_asset(monkeypatch, tmp_path):
    service = MediaGenerationService()
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "synthetic-test-key")
    service._client = SimpleNamespace(
        interactions=SimpleNamespace(
            create=lambda **kwargs: SimpleNamespace(
                output_image=SimpleNamespace(
                    data=base64.b64encode(
                        b"\x89PNG\r\n\x1a\nactual-image-bytes"
                    ).decode("ascii"),
                    mime_type="image/png",
                )
            )
        )
    )
    monkeypatch.setattr(settings, "MEDIA_STORAGE_DIR", tmp_path)

    media = asyncio.run(service.generate_image("A professional office visual"))
    asset = service.resolve_local_asset(media["media_url"])

    assert media["mime_type"] == "image/png"
    assert asset is not None
    assert asset[0].read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_image_generation_client_uses_bounded_http_timeout(monkeypatch):
    from google import genai

    received = {}

    def create_client(**kwargs):
        received.update(kwargs)
        return object()

    monkeypatch.setattr(settings, "GEMINI_API_KEY", "synthetic-image-timeout-test-key")
    monkeypatch.setattr(genai, "Client", create_client)
    service = MediaGenerationService()

    assert service._client_for_generation() is not None
    assert received["http_options"].timeout == GEMINI_IMAGE_REQUEST_TIMEOUT_MS


@pytest.mark.parametrize(
    ("content", "content_type"),
    [
        (b"not an image", "image/png"),
        (b"\x89PNG\r\n\x1a\noversized", "text/plain"),
    ],
)
def test_upload_rejects_mismatched_image_content(content, content_type):
    with pytest.raises(MediaGenerationError):
        MediaGenerationService().save_uploaded_image(content, content_type)


def test_uploaded_image_can_be_attached_to_a_draft(client, monkeypatch, tmp_path):
    from app.services.gemini_service import gemini_service

    async def generate_post(**kwargs):
        return {
            "message": "A generated draft for image review.",
            "media_url": None,
            "source": "gemini_api",
        }

    monkeypatch.setattr(gemini_service, "generate_social_post", generate_post)
    monkeypatch.setattr(settings, "MEDIA_STORAGE_DIR", tmp_path)
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "phase-two-admin@example.com",
            "password": "A-strong-test-password-123",
        },
    )
    assert login.status_code == 200
    client.headers["Authorization"] = "Bearer " + login.json()["access_token"]

    draft = client.post(
        "/api/v1/posts/generate-draft",
        json={
            "page_id": 1,
            "topic": "Admin uploaded image",
            "language": "en",
            "include_image": False,
            "request_id": "uploadable-image-draft",
        },
    )
    assert draft.status_code == 200

    upload = client.post(
        "/api/v1/posts/media/upload",
        files={"file": ("approved.png", b"\x89PNG\r\n\x1a\napproved-image", "image/png")},
    )
    assert upload.status_code == 200
    media_url = upload.json()["media_url"]

    updated = client.put(
        f"/api/v1/posts/{draft.json()['id']}/draft",
        json={"message": "A reviewed caption with an approved visual.", "media_url": media_url},
    )
    assert updated.status_code == 200
    assert updated.json()["media_url"] == media_url
    assert updated.json()["media_status"] == "uploaded"
    assert (tmp_path / "uploads" / media_url.rsplit("/", 1)[-1]).is_file()
