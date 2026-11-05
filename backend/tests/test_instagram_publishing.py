import asyncio
import io

import pytest
from PIL import Image


def _png_bytes():
    output = io.BytesIO()
    Image.new("RGBA", (16, 16), (20, 120, 180, 128)).save(output, format="PNG")
    return output.getvalue()


def test_local_png_is_converted_to_jpeg_and_public_https_url(monkeypatch, tmp_path):
    from app.config import settings
    from app.services.media_generation import media_generation_service
    from app.services.meta_client import MetaGraphClient

    monkeypatch.setattr(settings, "MEDIA_STORAGE_DIR", tmp_path)
    monkeypatch.setattr(settings, "MEDIA_PUBLIC_BASE_URL", "https://media.example.com")
    image = media_generation_service.save_uploaded_image(_png_bytes(), "image/png")

    compatible_url = media_generation_service.instagram_compatible_media_url(image["media_url"])
    local_asset = media_generation_service.resolve_local_asset(compatible_url)

    assert compatible_url.endswith(".jpg")
    assert local_asset is not None
    assert local_asset[1] == "image/jpeg"
    assert MetaGraphClient.public_media_url(compatible_url) == (
        f"https://media.example.com{compatible_url}"
    )


def test_instagram_public_media_url_rejects_non_https_or_private_hosts(monkeypatch):
    from app.config import settings
    from app.services.meta_client import MetaAPIError, MetaGraphClient

    monkeypatch.setattr(settings, "MEDIA_PUBLIC_BASE_URL", "")
    with pytest.raises(MetaAPIError, match="HTTPS"):
        MetaGraphClient.public_media_url("http://images.example.com/photo.jpg")
    with pytest.raises(MetaAPIError, match="public"):
        MetaGraphClient.public_media_url("https://127.0.0.1/photo.jpg")


def test_instagram_publish_creates_processes_publishes_and_verifies_container(monkeypatch):
    from app.config import settings
    from app.services.meta_client import MetaGraphClient

    monkeypatch.setattr(settings, "SIMULATION_MODE", False)
    client = MetaGraphClient()
    client.public_media_url = lambda _: "https://media.example.com/photo.jpg"
    requests = []

    async def request_json(method, url, *, params=None, data=None, files=None, timeout=15.0):
        requests.append((method, url, params, data))
        if url.endswith("/media"):
            return {"id": "container-id"}
        if url.endswith("/container-id"):
            return {"id": "container-id", "status_code": "FINISHED"}
        if url.endswith("/media_publish"):
            return {"id": "published-media-id"}
        return {
            "id": "published-media-id",
            "permalink": "https://instagram.com/p/verified/",
        }

    client._request_json = request_json
    result = asyncio.run(
        client.publish_instagram_image(
            "ig-account-id",
            "Reviewed caption",
            "/media/generated/photo.jpg",
            "synthetic-page-token",
        )
    )

    assert result == {
        "id": "published-media-id",
        "permalink_url": "https://instagram.com/p/verified/",
        "verified": True,
    }
    assert [request[0] for request in requests] == ["POST", "GET", "POST", "GET"]
    assert requests[0][3]["image_url"] == "https://media.example.com/photo.jpg"
    assert requests[0][3]["caption"] == "Reviewed caption"
    assert requests[2][3]["creation_id"] == "container-id"


def test_instagram_publish_transport_error_is_marked_uncertain(monkeypatch):
    from app.config import settings
    from app.services.meta_client import MetaAPIError, MetaGraphClient

    monkeypatch.setattr(settings, "SIMULATION_MODE", False)
    client = MetaGraphClient()
    client.public_media_url = lambda _: "https://media.example.com/photo.jpg"

    async def request_json(method, url, **kwargs):
        if url.endswith("/media"):
            return {"id": "container-id"}
        if url.endswith("/container-id"):
            return {"id": "container-id", "status_code": "FINISHED"}
        raise MetaAPIError("Meta Graph API request timed out")

    client._request_json = request_json
    with pytest.raises(MetaAPIError) as error:
        asyncio.run(
            client.publish_instagram_image(
                "ig-account-id",
                "Reviewed caption",
                "/media/generated/photo.jpg",
                "synthetic-page-token",
            )
        )

    assert error.value.publication_uncertain is True
