import asyncio
import json
from types import SimpleNamespace

import pytest

from app.config import settings
from app.services.gemini_service import GeminiService, GeminiServiceError


def test_missing_api_key_requires_explicit_fallback_opt_in(monkeypatch):
    service = GeminiService()
    service._client = None
    monkeypatch.setattr(settings, "ENABLE_LOCAL_AI_FALLBACK", False)

    with pytest.raises(GeminiServiceError, match="API key is not configured"):
        asyncio.run(service.generate_comment_reply("Hello"))

    monkeypatch.setattr(settings, "ENABLE_LOCAL_AI_FALLBACK", True)
    result = asyncio.run(service.generate_comment_reply("Hello"))
    assert result["source"] == "local_fallback"
    assert result["fallback_reason"] == "Gemini API key is not configured"


def test_gemini_comment_generation_is_async_and_validates_response(monkeypatch):
    service = GeminiService()
    monkeypatch.setattr(settings, "ENABLE_LOCAL_AI_FALLBACK", False)
    calls = []

    class Models:
        async def generate_content(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                text=json.dumps(
                    {
                        "detected_language": "en",
                        "sentiment": "question",
                        "reply": "Please message us for details.",
                        "confidence": 0.9,
                    }
                )
            )

    service._client = SimpleNamespace(aio=SimpleNamespace(models=Models()))
    result = asyncio.run(service.generate_comment_reply("What is the price?"))

    assert result["source"] == "gemini_api"
    assert result["reply"] == "Please message us for details."
    assert calls[0]["config"]["response_mime_type"] == "application/json"


def test_invalid_gemini_response_is_not_hidden_without_fallback(monkeypatch):
    service = GeminiService()
    monkeypatch.setattr(settings, "ENABLE_LOCAL_AI_FALLBACK", False)

    class Models:
        async def generate_content(self, **kwargs):
            return SimpleNamespace(text="not json")

    service._client = SimpleNamespace(aio=SimpleNamespace(models=Models()))
    with pytest.raises(GeminiServiceError, match="invalid reply data"):
        asyncio.run(service.generate_comment_reply("Hello"))


def test_local_post_template_is_opt_in_and_explicit(monkeypatch):
    service = GeminiService()
    service._client = None
    monkeypatch.setattr(settings, "ENABLE_LOCAL_AI_FALLBACK", True)

    result = asyncio.run(service.generate_social_post(topic="New product", language="en"))

    assert result["source"] == "local_fallback"
    assert result["fallback_reason"] == "Gemini API key is not configured"
    assert "New product" in result["message"]
    assert result["media_url"] is None
