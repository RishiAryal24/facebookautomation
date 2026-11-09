import asyncio
import json
import logging
import re
import time
from difflib import SequenceMatcher
from typing import Any, Callable, Dict, List, Optional

import httpx
from google.genai import types
from google.genai.errors import APIError

from app.config import settings
from app.services.brand_knowledge import build_brand_profile, find_relevant_product


logger = logging.getLogger(__name__)
GEMINI_REQUEST_TIMEOUT_MS = 120_000


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
You are an experienced business editor writing Facebook Page drafts. Write with
specificity, natural rhythm, and the judgment of a knowledgeable marketing
professional; do not claim that a person wrote the content. Use only verified
facts supplied in the request. Never invent product features, prices, discounts,
availability, integrations, customer stories, results, achievements, or metrics.
Do not use generic promotional slogans, excessive emojis, or hashtags as filler.
Avoid phrases such as "Unlock your potential", "Revolutionize your business",
"In today's digital world", "Take your business to the next level", and
"Game-changing solutions".
Keep the requested language and length. Return the requested JSON only.
"""


class GeminiServiceError(RuntimeError):
    """Gemini is unavailable or returned content that did not meet the contract."""


class GeminiService:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.model_name = settings.GEMINI_MODEL
        self.fallback_model_name = settings.GEMINI_FALLBACK_MODEL
        self._client = None
        if self.api_key:
            from google import genai

            self._client = genai.Client(
                api_key=self.api_key,
                http_options=types.HttpOptions(timeout=GEMINI_REQUEST_TIMEOUT_MS),
            )

    def _log_api_error(
        self,
        operation: str,
        error: Exception,
        model_name: Optional[str] = None,
        duration_seconds: Optional[float] = None,
    ) -> None:
        message = str(getattr(error, "message", "") or error)
        if self.api_key:
            message = message.replace(self.api_key, "[redacted]")
        logger.warning(
            "Gemini %s failed: model=%s code=%s status=%s error_type=%s duration_seconds=%s message=%s",
            operation,
            model_name or self.model_name,
            getattr(error, "code", None),
            getattr(error, "status", None),
            type(error).__name__,
            f"{duration_seconds:.2f}" if duration_seconds is not None else "unknown",
            message[:500],
        )

    @staticmethod
    def _is_transient_api_error(error: APIError) -> bool:
        return error.code == 429 or (
            isinstance(error.code, int) and 500 <= error.code < 600
        )

    async def _generate_content_with_fallback(
        self,
        *,
        operation: str,
        contents: str,
        system_instruction: str,
    ) -> Any:
        models = [self.model_name]
        if self.fallback_model_name and self.fallback_model_name not in models:
            models.append(self.fallback_model_name)

        for index, model_name in enumerate(models):
            model_attempts = 2 if index > 0 else 1
            for attempt in range(model_attempts):
                try:
                    started_at = time.monotonic()
                    response = await self._client.aio.models.generate_content(
                        model=model_name,
                        contents=contents,
                        config={
                            "system_instruction": system_instruction,
                            "response_mime_type": "application/json",
                        },
                    )
                    logger.info(
                        "Gemini %s succeeded: model=%s duration_seconds=%.2f",
                        operation,
                        model_name,
                        time.monotonic() - started_at,
                    )
                    return response
                except (APIError, httpx.HTTPError) as exc:
                    self._log_api_error(
                        operation,
                        exc,
                        model_name,
                        time.monotonic() - started_at,
                    )
                    transient = (
                        self._is_transient_api_error(exc)
                        if isinstance(exc, APIError)
                        else isinstance(exc, (httpx.TimeoutException, httpx.TransportError))
                    )
                    if not transient:
                        raise GeminiServiceError("Gemini request failed") from exc
                    if attempt + 1 < model_attempts:
                        logger.info(
                            "Gemini %s retrying fallback model=%s after transient provider error",
                            operation,
                            model_name,
                        )
                        await asyncio.sleep(1)
                        continue
                    if index + 1 < len(models):
                        logger.info(
                            "Gemini %s switching to fallback model=%s after transient provider error",
                            operation,
                            models[index + 1],
                        )

        raise GeminiServiceError(
            "Gemini is temporarily unavailable across the configured models. "
            "Please try again shortly."
        )

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
            response = await self._generate_content_with_fallback(
                operation="comment generation",
                contents=prompt,
                system_instruction=BILINGUAL_SYSTEM_PROMPT,
            )
        except GeminiServiceError as exc:
            return self._fallback_or_raise(fallback, str(exc))

        try:
            result = self._validate_comment_result(json.loads(response.text or ""))
        except (json.JSONDecodeError, TypeError, GeminiServiceError):
            return self._fallback_or_raise(fallback, "Gemini returned invalid reply data")
        return result

    @staticmethod
    def _word_count(text: str) -> int:
        return len(re.findall(r"[\w]+(?:['’-][\w]+)*", text, re.UNICODE))

    @staticmethod
    def _length_range(content_length: str) -> tuple[int, int]:
        return {
            "short": (60, 100),
            "standard": (120, 200),
            "detailed": (200, 300),
            "storytelling": (180, 350),
        }[content_length]

    @classmethod
    def _trim_to_word_range(cls, text: str, word_min: int, word_max: int) -> Optional[str]:
        current_count = cls._word_count(text)
        if word_min <= current_count <= word_max:
            return text
        if current_count < word_min:
            return None

        # 1. Paragraph-level trimming (preserving paragraph breaks)
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if len(paragraphs) > 2:
            trimmed_paras = list(paragraphs)
            while len(trimmed_paras) > 2 and cls._word_count("\n\n".join(trimmed_paras)) > word_max:
                trimmed_paras.pop(-2)
                c = cls._word_count("\n\n".join(trimmed_paras))
                if word_min <= c <= word_max:
                    return "\n\n".join(trimmed_paras)

        # 2. Sentence-level trimming (preserving final CTA/hashtags)
        sentences = re.split(r'(?<=[.!?।])\s+', text)
        if len(sentences) > 2:
            trimmed_sentences = list(sentences)
            while len(trimmed_sentences) > 2 and cls._word_count(" ".join(trimmed_sentences)) > word_max:
                trimmed_sentences.pop(-2)
                c = cls._word_count(" ".join(trimmed_sentences))
                if word_min <= c <= word_max:
                    return " ".join(trimmed_sentences)

        # 3. Fallback: remove sentences from the end
        if len(sentences) > 1:
            trimmed_sentences = list(sentences)
            while len(trimmed_sentences) > 1 and cls._word_count(" ".join(trimmed_sentences)) > word_max:
                trimmed_sentences.pop(-1)
                c = cls._word_count(" ".join(trimmed_sentences))
                if word_min <= c <= word_max:
                    return " ".join(trimmed_sentences)

        return None

    async def generate_social_post(
        self,
        brand_context: str = "",
        topic: Optional[str] = None,
        language: str = "en",
        tone: str = "promotional",
        category: Optional[str] = None,
        recent_posts: Optional[List[str]] = None,
        content_length: str = "standard",
        brand_profile: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if content_length not in {"short", "standard", "detailed", "storytelling"}:
            raise GeminiServiceError("Unsupported requested caption length")
        if not self._client:
            raise GeminiServiceError("Gemini API key is not configured")

        selected_topic = (topic or "Useful guidance for local businesses").strip()
        profile = build_brand_profile(brand_profile)
        relevant_product = find_relevant_product(selected_topic, profile)
        missing_facts: List[str] = []
        if relevant_product:
            product_name = relevant_product.get("name", "the selected product")
            if not relevant_product.get("description"):
                missing_facts.append(f"Verified description for {product_name}")
            if not relevant_product.get("approved_features"):
                missing_facts.append(f"Approved features for {product_name}")

        word_minimum, word_maximum = self._length_range(content_length)
        language_name = {
            "ne": "natural Nepali",
            "en": "natural English",
            "bilingual": "natural Nepali and English",
        }.get(language, "natural English")
        topic_guidance = ""
        normalized_topic = selected_topic.casefold()
        if any(term in normalized_topic for term in ("hospital", "hms", "clinic")):
            topic_guidance = (
                "Ground the post in real hospital operations such as patient registration, "
                "appointments, admissions, billing, records, or coordination. Do not claim "
                "the product supports a workflow unless its verified product record says so."
            )
        elif any(term in normalized_topic for term in ("analytics", "insight", "data")):
            topic_guidance = (
                "Focus on useful reporting questions: KPI definitions, data accuracy, "
                "dashboards, reporting cadence, and how teams make decisions from evidence. "
                "Do not claim a feature unless verified."
            )
        elif any(term in normalized_topic for term in ("e-commerce", "ecommerce", "online store")):
            topic_guidance = (
                "Discuss practical online-store work such as order handling, inventory "
                "visibility, customer experience, and day-to-day operations. Do not assert "
                "that a named product provides a capability unless verified."
            )

        prompt = f"""
Brand knowledge profile (the only source of brand/product facts):
{json.dumps(profile, ensure_ascii=False, sort_keys=True)}
Additional administrator context:
{brand_context or "None"}
Topic: {selected_topic}
Relevant verified product record:
{json.dumps(relevant_product, ensure_ascii=False) if relevant_product else "No matching product record"}
For a named product, use only its description and approved_features in that
record for capability claims. Treat additional administrator context as tone
and background unless the same claim is explicitly verified in the product record.
Language: {language_name}
Brand tone: {tone}
Category: {category or "Choose the best fit"}
Caption length: {content_length}, exactly {word_minimum}-{word_maximum} words.
Target length guidance: aim for approximately {(word_minimum + word_maximum) // 2} words. Write concisely and strictly do not exceed {word_maximum} words.
Topic-specific direction: {topic_guidance or "Use a concrete, relevant business situation and explain it accurately."}
Past published/generated captions (avoid repeated hooks, structure, and wording):
{chr(10).join(f"- {item[:700]}" for item in (recent_posts or [])[:10]) or "None"}

Choose the most suitable structure from problem/explanation/solution, story/insight/
takeaway, educational explanation/example, feature/benefit/application, or question/
discussion/recommendation. Vary the hook and ending. Explain the customer's actual
problem and a practical response without implying unverified PyLoom product features.
Use realistic hypothetical situations only when clearly framed as examples, never as
real customer stories. Include a natural call to action only when it fits. Use at most
three relevant hashtags and no more than one emoji. Do not add a generic slogan.

Return JSON with:
- caption: complete post text in the requested language
- image_brief: a concrete, realistic visual concept for an AI image generator representing the post's core message. For software, analytics, data, or platforms (e.g. Insight360, SaaS, dashboards): describe a modern software UI/UX analytics dashboard displayed on a sleek high-resolution computer monitor or tablet, featuring vibrant upward financial line charts, colorful KPI metric cards, bar graphs, and detailed business intelligence widgets with clean modern corporate styling. For AI, cloud, or automation: describe an illuminated digital network infrastructure, automated robotic workflow systems, or high-tech server connectivity. For industry operations (healthcare, retail, logistics): describe the real-world operational environment with technology in action (e.g. modern clinical diagnostics workstation, automated smart fulfillment sorting conveyor). Never use abstract terms like "3D render of data", "glowing block", "translucent cylinder", or "3D visualization sculpture". Never describe empty conference rooms or furniture. Ensure the display screen, software interface, or active technology fills the frame with sharp detail.
- missing_facts: list of factual details an administrator should verify before publishing
- structure: short name of the selected structure
"""
        request_prompt = prompt
        last_error = "Gemini returned invalid post data"
        candidates: List[tuple[str, Dict[str, Any]]] = []
        for attempt in range(2):
            response = await self._generate_content_with_fallback(
                operation="social post generation",
                contents=request_prompt,
                system_instruction=SOCIAL_POST_SYSTEM_PROMPT,
            )

            try:
                result = json.loads(response.text or "")
            except (json.JSONDecodeError, TypeError) as exc:
                last_error = "Gemini returned invalid post data"
                if attempt == 1:
                    raise GeminiServiceError(last_error) from exc
                request_prompt = prompt + "\nThe previous response was not valid JSON. Return the required JSON object."
                continue

            if not isinstance(result, dict):
                last_error = "Gemini returned invalid post data"
                if attempt == 1:
                    raise GeminiServiceError(last_error)
                request_prompt = prompt + "\nThe previous response was not a JSON object. Return the required JSON object."
                continue

            message = result.get("caption")
            image_brief = result.get("image_brief")
            if not isinstance(message, str) or not message.strip():
                last_error = "Gemini returned an empty caption"
            elif len(message) > 63206:
                last_error = "Gemini returned a caption that exceeds Facebook's text limit"
            elif not isinstance(image_brief, str) or not image_brief.strip():
                last_error = "Gemini did not return a usable visual concept"
            else:
                candidates.append((message, result))
                count = self._word_count(message)
                if not word_minimum <= count <= word_maximum:
                    last_error = (
                        f"Gemini caption contains {count} words; "
                        f"{content_length} requires {word_minimum}-{word_maximum}"
                    )
                else:
                    normalized_message = re.sub(r"\s+", " ", message).casefold()
                    if any(
                        SequenceMatcher(
                            None,
                            normalized_message,
                            re.sub(r"\s+", " ", recent).casefold(),
                        ).ratio() >= 0.9
                        for recent in (recent_posts or [])
                    ):
                        last_error = "Gemini returned a caption too similar to recent content"
                    else:
                        returned_missing_facts = result.get("missing_facts", [])
                        if isinstance(returned_missing_facts, list):
                            missing_facts.extend(
                                fact.strip()
                                for fact in returned_missing_facts
                                if isinstance(fact, str) and fact.strip()
                            )
                        return {
                            "message": message.strip(),
                            "image_brief": image_brief.strip(),
                            "missing_facts": list(dict.fromkeys(missing_facts)),
                            "structure": str(result.get("structure") or "educational"),
                            "media_url": None,
                            "source": "gemini_api",
                        }
            if attempt == 1:
                # 1. If validation failed on final attempt, check if any overlong candidate can be trimmed cleanly
                for cand_message, cand_result in reversed(candidates):
                    trimmed = self._trim_to_word_range(cand_message, word_minimum, word_maximum)
                    if trimmed:
                        normalized_trimmed = re.sub(r"\s+", " ", trimmed).casefold()
                        if not any(
                            SequenceMatcher(
                                None,
                                normalized_trimmed,
                                re.sub(r"\s+", " ", recent).casefold(),
                            ).ratio() >= 0.9
                            for recent in (recent_posts or [])
                        ):
                            cand_image_brief = cand_result.get("image_brief") or "A clean, modern brand visual."
                            returned_missing_facts = cand_result.get("missing_facts", [])
                            if isinstance(returned_missing_facts, list):
                                missing_facts.extend(
                                    fact.strip()
                                    for fact in returned_missing_facts
                                    if isinstance(fact, str) and fact.strip()
                                )
                            logger.info(
                                "Trimmed overlong caption from %d to %d words for %s (%d-%d)",
                                self._word_count(cand_message),
                                self._word_count(trimmed),
                                content_length,
                                word_minimum,
                                word_maximum,
                            )
                            return {
                                "message": trimmed.strip(),
                                "image_brief": str(cand_image_brief).strip(),
                                "missing_facts": list(dict.fromkeys(missing_facts)),
                                "structure": str(cand_result.get("structure") or "educational"),
                                "media_url": None,
                                "source": "gemini_api",
                            }

                # 2. If trimming didn't apply (e.g. caption was slightly under, like 180-199 words for 200-300),
                # accept the best candidate within a reasonable grace margin (>= 75% of min, <= 125% of max)
                grace_minimum = max(20, int(word_minimum * 0.75))
                grace_maximum = int(word_maximum * 1.25)
                for cand_message, cand_result in reversed(candidates):
                    cand_count = self._word_count(cand_message)
                    if grace_minimum <= cand_count <= grace_maximum:
                        normalized_cand = re.sub(r"\s+", " ", cand_message).casefold()
                        if not any(
                            SequenceMatcher(
                                None,
                                normalized_cand,
                                re.sub(r"\s+", " ", recent).casefold(),
                            ).ratio() >= 0.9
                            for recent in (recent_posts or [])
                        ):
                            cand_image_brief = cand_result.get("image_brief") or "A clean, modern brand visual."
                            returned_missing_facts = cand_result.get("missing_facts", [])
                            if isinstance(returned_missing_facts, list):
                                missing_facts.extend(
                                    fact.strip()
                                    for fact in returned_missing_facts
                                    if isinstance(fact, str) and fact.strip()
                                )
                            logger.info(
                                "Accepted caption of %d words within grace margin (%d-%d) for %s (%d-%d)",
                                cand_count,
                                grace_minimum,
                                grace_maximum,
                                content_length,
                                word_minimum,
                                word_maximum,
                            )
                            return {
                                "message": cand_message.strip(),
                                "image_brief": str(cand_image_brief).strip(),
                                "missing_facts": list(dict.fromkeys(missing_facts)),
                                "structure": str(cand_result.get("structure") or "educational"),
                                "media_url": None,
                                "source": "gemini_api",
                            }

                raise GeminiServiceError(last_error)
            target_minimum = max(word_minimum, (word_minimum + word_maximum) // 2 - 8)
            target_maximum = min(word_maximum, (word_minimum + word_maximum) // 2 + 8)
            previous_caption = (
                f"\nPrevious caption to revise:\n{message.strip()[:3000]}"
                if isinstance(message, str) and message.strip()
                else ""
            )
            request_prompt = (
                prompt
                + f"\nThe previous response failed validation: {last_error}. "
                f"Rewrite the previous caption to {target_minimum}-{target_maximum} words "
                f"(the allowed range is {word_minimum}-{word_maximum}). Count the words "
                "before returning the required JSON fields."
                + previous_caption
            )
        raise GeminiServiceError(last_error)


gemini_service = GeminiService()
