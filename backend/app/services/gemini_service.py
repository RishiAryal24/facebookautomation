import json
import re
from difflib import SequenceMatcher
from typing import Any, Callable, Dict, List, Optional

from google.genai.errors import APIError

from app.config import settings


BILINGUAL_SYSTEM_PROMPT = """
You write concise, respectful replies for an authorized business Facebook Page.

Rules:
- Reply in natural Nepali for Nepali comments, including Romanized Nepali; use
  English for English comments and the dominant language for mixed comments.
- Follow the requested brand tone while staying truthful and professional.
- Use only facts present in the post or brand context. Do not invent prices,
  delivery promises, warranties, inventory, or contact details.
- Never claim that a direct message was sent or an action was completed unless
  the application confirms that action.
- For complaints, refund requests, accusations, safety issues, or uncertainty,
  recommend operator review rather than making commitments.
- Keep replies to one to three short sentences.

Return JSON with:
- detected_language: "en", "ne", or "romanized_ne"
- sentiment: "positive", "question", "neutral", or "negative"
- reply: a string
- confidence: a number between 0 and 1
"""

SOCIAL_POST_SYSTEM_PROMPT = """
Write accurate, non-deceptive Facebook Page post drafts. Do not invent product
claims, prices, discounts, availability, delivery promises, or customer results
that are absent from the provided context. Do not describe the draft as already
published. Keep the requested language and tone.
"""


class GeminiServiceError(RuntimeError):
    """Gemini is unavailable or returned content that did not meet the contract."""


class GeminiService:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.model_name = settings.GEMINI_MODEL
        self._client = None
        if self.api_key:
            from google import genai

            self._client = genai.Client(api_key=self.api_key)

    def _is_devanagari(self, text: str) -> bool:
        return bool(re.search(r"[\u0900-\u097f]", text))

    def _fallback_or_raise(
        self,
        fallback_factory: Callable[[], Dict[str, Any]],
        reason: str,
    ) -> Dict[str, Any]:
        if not settings.ENABLE_LOCAL_AI_FALLBACK:
            raise GeminiServiceError(reason)
        result = fallback_factory()
        result["source"] = "local_fallback"
        result["fallback_reason"] = reason
        return result

    def _generate_fallback_response(
        self,
        comment_text: str,
        target_language: Optional[str] = None,
    ) -> Dict[str, Any]:
        lower_comment = comment_text.lower()
        romanized_words = ("kati", "parcha", "hunchha", "huncha", "thau", "ramro")
        is_romanized_nepali = any(word in lower_comment for word in romanized_words)
        is_nepali = (
            self._is_devanagari(comment_text)
            or is_romanized_nepali
            or target_language in ("ne", "bilingual")
        )
        is_question = any(
            word in lower_comment
            for word in ("price", "cost", "kati", "rate", "कति", "मूल्य", "where", "कहाँ")
        )
        is_positive = any(
            word in lower_comment
            for word in ("nice", "good", "great", "wow", "ramro", "राम्रो", "बधाई")
        )

        if is_nepali:
            reply = (
                "नमस्ते! मूल्य तथा थप जानकारीका लागि कृपया हामीलाई सिधै मेसेज गर्नुहोस्। 🙏"
                if is_question
                else "धेरै धेरै धन्यवाद! तपाईंको प्रतिक्रियाको हामी कदर गर्छौँ। ❤️"
                if is_positive
                else "प्रतिक्रियाका लागि धन्यवाद। थप सहयोग चाहनुहुन्छ भने हामीलाई सिधै मेसेज गर्नुहोस्। 🙏"
            )
            language = "romanized_ne" if is_romanized_nepali else "ne"
        else:
            reply = (
                "Thanks for your interest. Please message us directly for current pricing and details."
                if is_question
                else "Thank you for the kind feedback. We appreciate your support!"
                if is_positive
                else "Thanks for reaching out. Please message us directly if you need more information."
            )
            language = "en"

        return {
            "detected_language": language,
            "sentiment": "question" if is_question else "positive" if is_positive else "neutral",
            "reply": reply,
            "confidence": 0.6,
            "source": "local_fallback",
        }

    def _validate_comment_result(self, result: Any) -> Dict[str, Any]:
        if not isinstance(result, dict):
            raise GeminiServiceError("Gemini returned a non-object reply")
        language = result.get("detected_language")
        sentiment = result.get("sentiment")
        reply = result.get("reply")
        confidence = result.get("confidence")
        if language not in {"en", "ne", "romanized_ne"}:
            raise GeminiServiceError("Gemini returned an unsupported language value")
        if sentiment not in {"positive", "question", "neutral", "negative"}:
            raise GeminiServiceError("Gemini returned an unsupported sentiment value")
        if not isinstance(reply, str) or not reply.strip():
            raise GeminiServiceError("Gemini returned an empty reply")
        if (
            isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not 0 <= confidence <= 1
        ):
            raise GeminiServiceError("Gemini returned an invalid confidence value")
        return {
            "detected_language": language,
            "sentiment": sentiment,
            "reply": reply.strip(),
            "confidence": float(confidence),
            "source": "gemini_api",
        }

    async def generate_comment_reply(
        self,
        comment_text: str,
        post_context: str = "",
        brand_context: str = "",
        tone: str = "friendly",
        target_language: Optional[str] = None,
        custom_instructions: Optional[str] = None,
    ) -> Dict[str, Any]:
        fallback = lambda: self._generate_fallback_response(comment_text, target_language)
        if not self._client:
            return self._fallback_or_raise(
                fallback,
                "Gemini API key is not configured",
            )

        prompt = f"""
Post context: {post_context or "Not provided"}
Brand context: {brand_context or "Not provided"}
Requested tone: {tone}
Requested language: {target_language or "Match the incoming comment"}
Additional operator instructions: {custom_instructions or "None"}
Incoming comment:
{comment_text}
"""
        try:
            response = await self._client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config={
                    "system_instruction": BILINGUAL_SYSTEM_PROMPT,
                    "response_mime_type": "application/json",
                },
            )
        except APIError:
            return self._fallback_or_raise(fallback, "Gemini request failed")

        try:
            result = self._validate_comment_result(json.loads(response.text or ""))
        except (json.JSONDecodeError, TypeError, GeminiServiceError):
            return self._fallback_or_raise(fallback, "Gemini returned invalid reply data")
        return result

    def _generate_fallback_post(
        self,
        topic: Optional[str],
        language: str,
    ) -> Dict[str, Any]:
        if language == "ne":
            message = (
                f"✨ {topic or 'हाम्रो नयाँ जानकारी'} ✨\n\n"
                "थप जानकारीका लागि हामीलाई सिधै मेसेज गर्नुहोस्।\n"
                "#PyLoom #Nepal"
            )
        elif language == "bilingual":
            message = (
                f"✨ {topic or 'A new update / नयाँ जानकारी'} ✨\n\n"
                "थप जानकारीका लागि हामीलाई सिधै मेसेज गर्नुहोस्।\n"
                "Message us directly for more information.\n"
                "#PyLoom #Nepal"
            )
        else:
            message = (
                f"✨ {topic or 'A new update'} ✨\n\n"
                "Message us directly for more information.\n"
                "#PyLoom"
            )
        return {
            "message": message,
            "media_url": None,
            "source": "local_fallback",
        }

    async def generate_social_post(
        self,
        brand_context: str = "",
        topic: Optional[str] = None,
        language: str = "ne",
        tone: str = "promotional",
        category: Optional[str] = None,
        recent_posts: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        fallback = lambda: self._generate_fallback_post(topic, language)
        if not self._client:
            return self._fallback_or_raise(
                fallback,
                "Gemini API key is not configured",
            )

        prompt = f"""
Brand context: {brand_context or "Not provided"}
Topic: {topic or "Product information and customer support"}
Language: {"Nepali" if language == "ne" else "English" if language == "en" else "Bilingual Nepali and English"}
Tone: {tone}
Content category: {category or "Choose the most relevant category"}
Recently generated captions (do not repeat or closely paraphrase):
{chr(10).join(f"- {item[:500]}" for item in (recent_posts or [])[:10]) or "None"}
Write a natural, professional caption with relevant hashtags and a clear,
truthful call to action. Do not invent achievements, testimonials, prices,
discounts, offers, availability, or customer results. Return only the post text.
"""
        try:
            response = await self._client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config={"system_instruction": SOCIAL_POST_SYSTEM_PROMPT},
            )
        except APIError:
            return self._fallback_or_raise(fallback, "Gemini request failed")

        message = (response.text or "").strip()
        if not message:
            return self._fallback_or_raise(fallback, "Gemini returned an empty post")
        if len(message) > 63206:
            raise GeminiServiceError("Gemini returned a caption that exceeds Facebook's text limit")
        if not re.search(r"#\w+", message, re.UNICODE):
            raise GeminiServiceError("Gemini caption did not include relevant hashtags")
        normalized_message = re.sub(r"\s+", " ", message).casefold()
        if any(
            SequenceMatcher(
                None,
                normalized_message,
                re.sub(r"\s+", " ", recent).casefold(),
            ).ratio() >= 0.9
            for recent in (recent_posts or [])
        ):
            raise GeminiServiceError(
                "Gemini returned a caption too similar to recently generated content"
            )
        return {
            "message": message,
            "media_url": None,
            "source": "gemini_api",
        }


gemini_service = GeminiService()
