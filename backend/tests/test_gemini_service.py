import asyncio
import json
import logging
from types import SimpleNamespace

import pytest
import httpx
from google.genai.errors import APIError

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


def test_social_post_generation_requires_gemini_instead_of_generic_fallback(monkeypatch):
    service = GeminiService()
    service._client = None
    monkeypatch.setattr(settings, "ENABLE_LOCAL_AI_FALLBACK", True)

    with pytest.raises(GeminiServiceError, match="API key is not configured"):
        asyncio.run(service.generate_social_post(topic="New product", language="en"))


def test_social_post_logs_sanitized_provider_error(caplog):
    service = GeminiService()
    service.api_key = "test-api-key"
    provider_error = APIError(
        404,
        {
            "error": {
                "message": "Model unavailable for test-api-key",
                "status": "NOT_FOUND",
            }
        },
    )

    class Models:
        async def generate_content(self, **kwargs):
            raise provider_error

    service._client = SimpleNamespace(aio=SimpleNamespace(models=Models()))
    with caplog.at_level(logging.WARNING, logger="app.services.gemini_service"):
        with pytest.raises(GeminiServiceError, match="Gemini request failed"):
            asyncio.run(service.generate_social_post(topic="New product", language="en"))

    assert "code=404" in caplog.text
    assert "status=NOT_FOUND" in caplog.text
    assert "Model unavailable for [redacted]" in caplog.text
    assert "test-api-key" not in caplog.text


def test_social_post_fails_over_and_bounded_retry_handles_transient_provider_errors(monkeypatch, caplog):
    service = GeminiService()
    provider_error = APIError(
        503,
        {"error": {"message": "Service temporarily unavailable", "status": "UNAVAILABLE"}},
    )
    model_names = []

    class Models:
        async def generate_content(self, *, model, **kwargs):
            model_names.append(model)
            raise provider_error

    async def skip_backoff(_delay):
        return None

    monkeypatch.setattr("app.services.gemini_service.asyncio.sleep", skip_backoff)
    service._client = SimpleNamespace(aio=SimpleNamespace(models=Models()))
    with caplog.at_level(logging.WARNING, logger="app.services.gemini_service"):
        with pytest.raises(GeminiServiceError, match="temporarily unavailable"):
            asyncio.run(service.generate_social_post(topic="New product", language="en"))

    assert model_names == [
        service.model_name,
        service.fallback_model_name,
        service.fallback_model_name,
    ]
    assert "code=503" in caplog.text
    assert "status=UNAVAILABLE" in caplog.text


def test_social_post_succeeds_after_primary_model_overload(caplog):
    service = GeminiService()
    model_names = []
    caption = " ".join(f"detail{index}" for index in range(120))

    class Models:
        async def generate_content(self, *, model, **kwargs):
            model_names.append(model)
            if model == service.model_name:
                raise APIError(
                    503,
                    {"error": {"message": "Primary model is overloaded", "status": "UNAVAILABLE"}},
                )
            return SimpleNamespace(
                text=json.dumps(
                    {
                        "caption": caption,
                        "image_brief": "A clean editorial image about the selected topic.",
                        "missing_facts": [],
                        "structure": "educational",
                    }
                )
            )

    service._client = SimpleNamespace(aio=SimpleNamespace(models=Models()))
    with caplog.at_level(logging.INFO, logger="app.services.gemini_service"):
        result = asyncio.run(
            service.generate_social_post(topic="Business reporting", language="en")
        )

    assert result["source"] == "gemini_api"
    assert service._word_count(result["message"]) == 120
    assert model_names == [service.model_name, service.fallback_model_name]
    assert service.fallback_model_name in caplog.text


def test_social_post_retries_fallback_once_then_succeeds(monkeypatch):
    service = GeminiService()
    model_names = []
    caption = " ".join(f"detail{index}" for index in range(120))

    class Models:
        async def generate_content(self, *, model, **kwargs):
            model_names.append(model)
            if model == service.model_name or model_names.count(model) == 1:
                raise APIError(
                    503,
                    {"error": {"message": "Temporary provider overload", "status": "UNAVAILABLE"}},
                )
            return SimpleNamespace(
                text=json.dumps(
                    {
                        "caption": caption,
                        "image_brief": "A clean editorial image about the selected topic.",
                        "missing_facts": [],
                        "structure": "educational",
                    }
                )
            )

    async def skip_backoff(_delay):
        return None

    monkeypatch.setattr("app.services.gemini_service.asyncio.sleep", skip_backoff)
    service._client = SimpleNamespace(aio=SimpleNamespace(models=Models()))
    result = asyncio.run(
        service.generate_social_post(topic="Business reporting", language="en")
    )

    assert result["source"] == "gemini_api"
    assert service._word_count(result["message"]) == 120
    assert model_names == [
        service.model_name,
        service.fallback_model_name,
        service.fallback_model_name,
    ]


def test_social_post_fails_over_after_network_timeout():
    service = GeminiService()
    model_names = []
    caption = " ".join(f"detail{index}" for index in range(120))

    class Models:
        async def generate_content(self, *, model, **kwargs):
            model_names.append(model)
            if model == service.model_name:
                raise httpx.ReadTimeout("provider response timed out")
            return SimpleNamespace(
                text=json.dumps(
                    {
                        "caption": caption,
                        "image_brief": "A clean editorial image about the selected topic.",
                        "missing_facts": [],
                        "structure": "educational",
                    }
                )
            )

    service._client = SimpleNamespace(aio=SimpleNamespace(models=Models()))
    result = asyncio.run(service.generate_social_post(topic="Business reporting", language="en"))

    assert result["source"] == "gemini_api"
    assert model_names == [service.model_name, service.fallback_model_name]


def test_gemini_client_uses_bounded_http_timeout(monkeypatch):
    from google import genai

    from app.services.gemini_service import GEMINI_REQUEST_TIMEOUT_MS

    received = {}

    def create_client(**kwargs):
        received.update(kwargs)
        return object()

    monkeypatch.setattr(settings, "GEMINI_API_KEY", "synthetic-timeout-test-key")
    monkeypatch.setattr(genai, "Client", create_client)
    service = GeminiService()

    assert service._client is not None
    assert received["http_options"].timeout == GEMINI_REQUEST_TIMEOUT_MS


def test_social_post_obeys_standard_length_and_uses_verified_product_context(monkeypatch):
    service = GeminiService()
    calls = []
    caption = " ".join(f"detail{index}" for index in range(120))

    class Models:
        async def generate_content(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                text=json.dumps(
                    {
                        "caption": caption,
                        "image_brief": "A calm, professional hospital workflow illustration.",
                        "missing_facts": [],
                        "structure": "educational example",
                    }
                )
            )

    service._client = SimpleNamespace(aio=SimpleNamespace(models=Models()))
    result = asyncio.run(
        service.generate_social_post(
            topic="PyLoom AI HMS",
            language="en",
            content_length="standard",
        )
    )

    assert 120 <= service._word_count(result["message"]) <= 200
    assert result["missing_facts"] == [
        "Verified description for PyLoom AI HMS",
        "Approved features for PyLoom AI HMS",
    ]
    assert calls[0]["config"]["response_mime_type"] == "application/json"
    assert "hospital operations" in calls[0]["contents"].lower()
    assert "approved_features" in calls[0]["contents"]
    assert "exactly 120-200 words" in calls[0]["contents"]


def test_social_post_retries_caption_outside_selected_word_range():
    service = GeminiService()
    calls = []
    captions = [
        "Too short.",
        " ".join(f"detail{index}" for index in range(60)),
    ]

    class Models:
        async def generate_content(self, **kwargs):
            text = captions[len(calls)]
            calls.append(kwargs)
            return SimpleNamespace(
                text=json.dumps(
                    {
                        "caption": text,
                        "image_brief": "A clean editorial visual.",
                        "missing_facts": [],
                        "structure": "educational",
                    }
                )
            )

    service._client = SimpleNamespace(aio=SimpleNamespace(models=Models()))
    result = asyncio.run(
        service.generate_social_post(
            topic="Data Analytics",
            language="en",
            content_length="short",
        )
    )

    assert len(calls) == 2
    assert 60 <= service._word_count(result["message"]) <= 100
    assert "Previous caption to revise:" in calls[1]["contents"]
    assert "Too short." in calls[1]["contents"]
    assert "72-88 words" in calls[1]["contents"]


def test_social_post_retries_overlong_caption_with_a_tighter_target():
    service = GeminiService()
    calls = []
    captions = [
        " ".join(f"detail{index}" for index in range(250)),
        " ".join(f"detail{index}" for index in range(160)),
    ]

    class Models:
        async def generate_content(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                text=json.dumps(
                    {
                        "caption": captions[len(calls) - 1],
                        "image_brief": "A clean editorial image about the selected topic.",
                        "missing_facts": [],
                        "structure": "educational",
                    }
                )
            )

    service._client = SimpleNamespace(aio=SimpleNamespace(models=Models()))
    result = asyncio.run(
        service.generate_social_post(topic="Business reporting", language="en")
    )

    assert service._word_count(result["message"]) == 160
    assert "152-168 words" in calls[1]["contents"]
    assert "detail249" in calls[1]["contents"]
