import asyncio
import base64
import binascii
import io
import httpx
import logging
import mimetypes
import time
import uuid
from pathlib import Path
from typing import Dict, Optional, Tuple
from urllib.parse import urlsplit

from PIL import Image
from google.genai import types
from google.genai.errors import APIError

from app.config import settings


MAX_UPLOAD_BYTES = 10 * 1024 * 1024
GEMINI_IMAGE_REQUEST_TIMEOUT_MS = 180_000
logger = logging.getLogger(__name__)
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": (".jpg", b"\xff\xd8\xff"),
    "image/png": (".png", b"\x89PNG\r\n\x1a\n"),
}


class MediaGenerationError(RuntimeError):
    """Image generation or media validation failed."""


class MediaGenerationService:
    max_upload_bytes = MAX_UPLOAD_BYTES

    def __init__(self) -> None:
        self._client = None

    def _client_for_generation(self):
        if not settings.GEMINI_API_KEY:
            raise MediaGenerationError("GEMINI_API_KEY is required for image generation")
        if self._client is None:
            from google import genai

            self._client = genai.Client(
                api_key=settings.GEMINI_API_KEY,
                http_options=types.HttpOptions(timeout=GEMINI_IMAGE_REQUEST_TIMEOUT_MS),
            )
        return self._client

    async def generate_image(self, prompt: str) -> Dict[str, str]:
        started_at = time.monotonic()
        try:
            response = await asyncio.to_thread(
                self._client_for_generation().interactions.create,
                model=settings.GEMINI_IMAGE_MODEL,
                input=prompt,
            )
        except MediaGenerationError:
            raise
        except (APIError, httpx.HTTPError) as exc:
            logger.warning(
                "Gemini image generation failed: model=%s duration_seconds=%.2f error_type=%s",
                settings.GEMINI_IMAGE_MODEL,
                time.monotonic() - started_at,
                type(exc).__name__,
            )
            raise MediaGenerationError("The configured image-generation provider failed") from exc

        image = getattr(response, "output_image", None)
        encoded_image = getattr(image, "data", None)
        mime_type = getattr(image, "mime_type", None) or "image/png"
        try:
            image_bytes = base64.b64decode(encoded_image, validate=True) if encoded_image else None
        except (binascii.Error, ValueError) as exc:
            raise MediaGenerationError("The image provider returned invalid image data") from exc
        image_signature = ALLOWED_IMAGE_TYPES.get(mime_type)
        if (
            not image_bytes
            or not image_signature
            or len(image_bytes) > MAX_UPLOAD_BYTES
            or not image_bytes.startswith(image_signature[1])
        ):
            raise MediaGenerationError("The image provider returned no supported image asset")
        logger.info(
            "Gemini image generation succeeded: model=%s duration_seconds=%.2f",
            settings.GEMINI_IMAGE_MODEL,
            time.monotonic() - started_at,
        )
        return self._save_image(image_bytes, mime_type, "generated")

    def validate_upload(self, content: bytes, content_type: Optional[str]) -> str:
        if not content:
            raise MediaGenerationError("Choose a non-empty image file")
        if len(content) > MAX_UPLOAD_BYTES:
            raise MediaGenerationError("Image uploads must be 10 MB or smaller")
        if content_type not in ALLOWED_IMAGE_TYPES:
            raise MediaGenerationError("Upload a PNG or JPEG image")
        extension, signature = ALLOWED_IMAGE_TYPES[content_type]
        if not content.startswith(signature):
            raise MediaGenerationError("The uploaded file content does not match its image type")
        return extension

    def save_uploaded_image(self, content: bytes, content_type: Optional[str]) -> Dict[str, str]:
        extension = self.validate_upload(content, content_type)
        return self._save_image(content, content_type or "image/jpeg", "uploads", extension)

    def _save_image(
        self,
        content: bytes,
        mime_type: str,
        subdirectory: str,
        extension: Optional[str] = None,
    ) -> Dict[str, str]:
        extension = extension or mimetypes.guess_extension(mime_type) or ".png"
        if extension == ".jpe":
            extension = ".jpg"
        filename = f"{uuid.uuid4().hex}{extension}"
        asset_directory = settings.MEDIA_STORAGE_DIR / subdirectory
        asset_directory.mkdir(parents=True, exist_ok=True)
        try:
            (asset_directory / filename).write_bytes(content)
        except OSError as exc:
            raise MediaGenerationError("The media asset could not be stored") from exc
        return {
            "media_url": f"/media/{subdirectory}/{filename}",
            "mime_type": mime_type,
        }

    def resolve_local_asset(self, media_url: str) -> Optional[Tuple[Path, str]]:
        parsed = urlsplit(media_url)
        if (
            parsed.scheme
            or parsed.netloc
            or parsed.query
            or parsed.fragment
            or not parsed.path.startswith("/media/")
        ):
            return None
        relative_path = Path(parsed.path.removeprefix("/media/"))
        if len(relative_path.parts) != 2 or relative_path.parts[0] not in {"generated", "uploads"}:
            return None
        path = (settings.MEDIA_STORAGE_DIR / relative_path).resolve()
        if settings.MEDIA_STORAGE_DIR.resolve() not in path.parents or not path.is_file():
            return None
        mime_type = mimetypes.guess_type(path.name)[0]
        if mime_type not in {"image/png", "image/jpeg"}:
            return None
        return path, mime_type

    def instagram_compatible_media_url(self, media_url: str) -> str:
        local_asset = self.resolve_local_asset(media_url)
        if local_asset is None:
            path = urlsplit(media_url).path.lower()
            if not path.endswith((".jpg", ".jpeg")):
                raise MediaGenerationError(
                    "Instagram requires a publicly reachable JPEG image URL"
                )
            return media_url
        asset_path, mime_type = local_asset
        if mime_type == "image/jpeg":
            return media_url
        try:
            with Image.open(asset_path) as source:
                rgba = source.convert("RGBA")
                background = Image.new("RGB", rgba.size, "white")
                background.paste(rgba, mask=rgba.getchannel("A"))
                output = io.BytesIO()
                background.save(output, format="JPEG", quality=92, optimize=True)
        except OSError as exc:
            raise MediaGenerationError("The PNG image could not be converted for Instagram") from exc
        stored = self._save_image(output.getvalue(), "image/jpeg", "generated", ".jpg")
        return stored["media_url"]


media_generation_service = MediaGenerationService()
