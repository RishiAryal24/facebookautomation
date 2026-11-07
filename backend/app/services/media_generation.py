import asyncio
import base64
import binascii
import io
import logging
import mimetypes
import random
import time
import uuid
from pathlib import Path
from typing import Dict, Optional, Tuple
from urllib.parse import quote, urlsplit

import httpx
from PIL import Image
from google.genai import types
from google.genai.errors import APIError

from app.config import settings

logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
GEMINI_IMAGE_REQUEST_TIMEOUT_MS = 180_000
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
        provider = getattr(settings, "IMAGE_GENERATION_PROVIDER", "pollinations").lower()

        if provider == "gemini":
            try:
                return await self._generate_with_gemini(prompt)
            except MediaGenerationError as exc:
                logger.info(
                    "Gemini image generation unavailable (%s); falling back to Pollinations/FLUX",
                    exc,
                )
                return await self._generate_with_pollinations(prompt)

        return await self._generate_with_pollinations(prompt)

    async def _generate_with_pollinations(self, prompt: str) -> Dict[str, str]:
        """Generate high-quality 1024x1024 social visuals via Pollinations FLUX engine (Free Tier)."""
        clean_prompt = " ".join(prompt.strip().split())
        seed = random.randint(1000, 999999)
        url = (
            f"https://image.pollinations.ai/prompt/{quote(clean_prompt)}"
            f"?width=1024&height=1024&nologo=true&seed={seed}&model=flux"
        )
        headers = {
            "User-Agent": "PyLoom-Automation/1.0 (Facebook Community Management)",
            "Accept": "image/jpeg,image/png,image/*",
        }

        try:
            async with httpx.AsyncClient(timeout=40.0, follow_redirects=True) as client:
                res = await client.get(url, headers=headers)
                if res.status_code != 200:
                    raise MediaGenerationError(
                        f"Pollinations returned HTTP status {res.status_code}"
                    )
                content = res.content
        except httpx.TimeoutException as exc:
            raise MediaGenerationError(
                "Image generation timed out. Please try again or upload an image manually."
            ) from exc
        except httpx.HTTPError as exc:
            raise MediaGenerationError(f"Image generation network error: {exc}") from exc

        if not content or len(content) < 1000:
            raise MediaGenerationError("The image provider returned incomplete image data")

        mime_type = "image/jpeg"
        extension = ".jpg"
        try:
            with Image.open(io.BytesIO(content)) as pil_img:
                pil_format = (pil_img.format or "JPEG").upper()
                if pil_format == "PNG":
                    mime_type = "image/png"
                    extension = ".png"
                else:
                    mime_type = "image/jpeg"
                    extension = ".jpg"
        except Exception as exc:
            raise MediaGenerationError("The provider returned an unrecognized image file") from exc

        return self._save_image(content, mime_type, "generated", extension)

    async def _generate_with_gemini(self, prompt: str) -> Dict[str, str]:
        """Generate images via Google GenAI SDK (requires Pay-as-you-go billing in Google AI Studio)."""
        started_at = time.monotonic()
        client = self._client_for_generation()
        model_name = settings.GEMINI_IMAGE_MODEL or "gemini-2.5-flash-image"

        try:
            response = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=model_name,
                    contents=prompt,
                ),
                timeout=25.0,
            )
        except asyncio.TimeoutError as exc:
            logger.warning(
                "Gemini image generation timed out: model=%s duration_seconds=%.2f",
                model_name,
                time.monotonic() - started_at,
            )
            raise MediaGenerationError(
                "Image generation timed out. You can upload an image manually or publish text-only."
            ) from exc
        except APIError as exc:
            logger.warning(
                "Gemini image generation API error: model=%s duration_seconds=%.2f error=%s",
                model_name,
                time.monotonic() - started_at,
                exc,
            )
            msg = str(exc)
            if "RESOURCE_EXHAUSTED" in msg or "429" in msg or "quota" in msg.lower():
                raise MediaGenerationError(
                    "Google AI Studio Free Tier has a quota of 0 for image generation. "
                    "Consumer Gemini Pro subscriptions do not apply to developer API keys; "
                    "a Pay-as-you-go billing account must be linked in Google AI Studio."
                ) from exc
            raise MediaGenerationError(
                f"Image generation provider error: {getattr(exc, 'message', str(exc))}"
            ) from exc
        except MediaGenerationError:
            raise
        except (httpx.HTTPError, Exception) as exc:
            logger.warning(
                "Gemini image generation failed: model=%s duration_seconds=%.2f error_type=%s",
                model_name,
                time.monotonic() - started_at,
                type(exc).__name__,
            )
            raise MediaGenerationError(f"Image generation failed: {exc}") from exc

        image_bytes = None
        mime_type = "image/png"

        candidates = getattr(response, "candidates", None) or []
        for cand in candidates:
            content = getattr(cand, "content", None)
            parts = getattr(content, "parts", None) or []
            for part in parts:
                inline_data = getattr(part, "inline_data", None)
                if inline_data:
                    image_bytes = getattr(inline_data, "data", None)
                    mime_type = getattr(inline_data, "mime_type", None) or "image/png"
                    if isinstance(image_bytes, str):
                        try:
                            image_bytes = base64.b64decode(image_bytes)
                        except Exception:
                            pass
                    if image_bytes:
                        break
                if hasattr(part, "as_image"):
                    try:
                        pil_img = part.as_image()
                        buf = io.BytesIO()
                        pil_img.save(buf, format="PNG")
                        image_bytes = buf.getvalue()
                        mime_type = "image/png"
                        break
                    except Exception:
                        pass
            if image_bytes:
                break

        if not image_bytes:
            image = getattr(response, "output_image", None)
            encoded_image = getattr(image, "data", None)
            mime_type = getattr(image, "mime_type", None) or mime_type
            if encoded_image:
                try:
                    image_bytes = base64.b64decode(encoded_image, validate=True)
                except Exception:
                    pass

        if not image_bytes:
            raise MediaGenerationError("The image provider did not return any image asset")

        image_signature = ALLOWED_IMAGE_TYPES.get(mime_type)
        if not image_signature or len(image_bytes) > MAX_UPLOAD_BYTES or not image_bytes.startswith(image_signature[1]):
            try:
                with Image.open(io.BytesIO(image_bytes)) as pil_img:
                    buf = io.BytesIO()
                    pil_img.save(buf, format="PNG")
                    image_bytes = buf.getvalue()
                    mime_type = "image/png"
            except Exception:
                raise MediaGenerationError("The image provider returned an unsupported image format")

        logger.info(
            "Gemini image generation succeeded: model=%s duration_seconds=%.2f",
            model_name,
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
            raise MediaGenerationError("Uploaded file contents do not match the expected image signature")
        try:
            with Image.open(io.BytesIO(content)) as pil_image:
                pil_image.verify()
        except Exception as exc:
            raise MediaGenerationError("Uploaded image cannot be parsed safely") from exc
        return extension

    def save_upload(self, content: bytes, content_type: str) -> Dict[str, str]:
        extension = self.validate_upload(content, content_type)
        return self._save_image(content, content_type, "uploads", extension)

    def _save_image(
        self,
        content: bytes,
        content_type: str,
        kind: str,
        extension: Optional[str] = None,
    ) -> Dict[str, str]:
        settings.MEDIA_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        resolved_extension = extension or ALLOWED_IMAGE_TYPES.get(content_type, (".png", b""))[0]
        filename = f"{kind}_{uuid.uuid4().hex}{resolved_extension}"
        destination = settings.MEDIA_STORAGE_DIR / filename
        destination.write_bytes(content)

        base_url = (settings.MEDIA_PUBLIC_BASE_URL or "").rstrip("/")
        media_url = f"{base_url}/media/{filename}" if base_url else f"/media/{filename}"
        return {
            "media_url": media_url,
            "filename": filename,
            "mime_type": content_type,
            "file_size": len(content),
        }

    def delete_media_file(self, media_url: Optional[str]) -> bool:
        if not media_url:
            return False
        path_part = urlsplit(media_url).path
        filename = Path(path_part).name
        if not filename:
            return False
        candidate = (settings.MEDIA_STORAGE_DIR / filename).resolve()
        if candidate.parent != settings.MEDIA_STORAGE_DIR.resolve():
            return False
        if not candidate.exists():
            return False
        candidate.unlink()
        return True
