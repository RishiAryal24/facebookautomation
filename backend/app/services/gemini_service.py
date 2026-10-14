import os
import re
from typing import Dict, Any, Optional
from app.config import settings

# System instructions for bilingual Facebook comment response
BILINGUAL_SYSTEM_PROMPT = """
You are an expert social media manager for a business Facebook Page managed by PyLoom Technologies.
Your job is to generate polite, helpful, context-aware, and authentic responses to comments on Facebook posts.

IMPORTANT RULES:
1. LANGUAGE DETECTION & MATCHING:
   - If the user comments in Nepali (Devanagari script, e.g. "मूल्य कति हो?"), reply in natural, polite Nepali.
   - If the user comments in Romanized Nepali (e.g. "kati parcha hola?", "delivery hunchha?"), reply in natural polite Nepali (or polite Romanized Nepali if short and clear).
   - If the user comments in English, reply in natural, professional English.
   - If mixed, match the dominant language.
2. TONE & BRAND VOICE:
   - Adhere to the requested tone (Friendly, Professional, Support, or Promotional).
   - Never sound like a robotic generic bot. Sound like an attentive, warm business representative.
   - Always encourage a clear next step (e.g. "Please check your inbox (DM) for price and details!", or "Feel free to call/WhatsApp us!").
3. ACCURACY & CONTEXT:
   - Use the post context provided. If specific prices are not in the post, invite them to direct message (DM) or leave a contact number.
   - Keep comments concise (typically 1 to 3 sentences maximum, ideal for Facebook comment threads).
4. OUTPUT FORMAT:
   Return a JSON structure with:
   - "detected_language": "en" | "ne" | "romanized_ne"
   - "sentiment": "positive" | "question" | "neutral" | "negative"
   - "reply": "<The response text>"
   - "confidence": 0.0 - 1.0
"""

class GeminiService:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY", "")
        self.model_name = settings.GEMINI_MODEL
        self._client = None
        if self.api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except Exception as e:
                print(f"Warning: Failed to initialize Gemini Client: {e}")

    def _is_devanagari(self, text: str) -> bool:
        # Check if text contains Devanagari Unicode range U+0900 to U+097F
        return bool(re.search(r'[\u0900-\u097f]', text))

    def _generate_fallback_response(
        self,
        comment_text: str,
        post_context: str,
        tone: str = "friendly",
        target_language: Optional[str] = None
    ) -> Dict[str, Any]:
        """High-quality realistic template fallback if API key is not configured or in sandbox mode."""
        is_nepali = self._is_devanagari(comment_text) or target_language == "ne"
        lower_comment = comment_text.lower()
        
        # Check intent
        is_price_inquiry = any(w in lower_comment for w in ["price", "cost", "kati", "rate", "कति", "मूल्य"])
        is_location_inquiry = any(w in lower_comment for w in ["where", "location", "address", "thau", "कहाँ", "ठेगाना"])
        is_positive = any(w in lower_comment for w in ["nice", "good", "great", "wow", "ramro", "राम्रो", "बधाई"])
        
        if is_nepali:
            lang = "ne"
            sentiment = "question" if (is_price_inquiry or is_location_inquiry) else "positive" if is_positive else "neutral"
            if is_price_inquiry:
                reply = "नमस्ते! कृपया थप जानकारी तथा मूल्यको लागि आफ्नो इनबक्स (DM) चेक गर्नुहोला। धन्यवाद! 🙏"
            elif is_location_inquiry:
                reply = "नमस्ते! हाम्रो ठेगाना र सम्पर्क विवरण इनबक्समा पठाएका छौँ, कृपया चेक गर्नुहोला। 🙏"
            elif is_positive:
                reply = "धेरै धेरै धन्यवाद! हजुरको साथ र मायाको लागि हामी सधैँ आभारी छौँ। ❤️"
            else:
                reply = "नमस्ते! प्रतिक्रियाको लागि हार्दिक धन्यवाद। थप जानकारीको लागि हामीलाई सिधै मेसेज गर्न सक्नुहुन्छ। 🙏"
        else:
            lang = "en"
            sentiment = "question" if (is_price_inquiry or is_location_inquiry) else "positive" if is_positive else "neutral"
            if is_price_inquiry:
                reply = "Hello! Thanks for your interest. We've sent you a direct message (DM) with full pricing and details. Please check your inbox! 😊"
            elif is_location_inquiry:
                reply = "Hi there! We have shared our exact location and contact details in your messages. Looking forward to serving you! 📍"
            elif is_positive:
                reply = "Thank you so much for the love and positive feedback! We truly appreciate your support! ❤️"
            else:
                reply = "Thank you for reaching out! Please feel free to send us a direct message for any assistance or inquiries. Have a wonderful day!"

        return {
            "detected_language": lang,
            "sentiment": sentiment,
            "reply": reply,
            "confidence": 0.95,
            "source": "smart_local_template"
        }

    async def generate_comment_reply(
        self,
        comment_text: str,
        post_context: str = "",
        brand_context: str = "",
        tone: str = "friendly",
        target_language: Optional[str] = None,
        custom_instructions: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate bilingual comment response using Google Gemini or intelligent fallback."""
        if not self._client:
            return self._generate_fallback_response(comment_text, post_context, tone, target_language)
            
        import json
        prompt = f"""
Post Context: {post_context or 'General brand promotion'}
Brand Context: {brand_context or 'PyLoom client business'}
Desired Tone: {tone}
Preferred Language Override: {target_language or 'Automatic matching'}
Custom Instructions: {custom_instructions or 'None'}

Incoming Facebook User Comment: "{comment_text}"

Generate the JSON response conforming to the system rules.
"""
        try:
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config={
                    "system_instruction": BILINGUAL_SYSTEM_PROMPT,
                    "response_mime_type": "application/json"
                }
            )
            raw_text = response.text
            parsed = json.loads(raw_text)
            parsed["source"] = "gemini_api"
            return parsed
        except Exception as e:
            print(f"Gemini API call failed, falling back to smart local template: {e}")
            return self._generate_fallback_response(comment_text, post_context, tone, target_language)

    async def generate_social_post(
        self,
        brand_context: str = "",
        topic: Optional[str] = None,
        language: str = "ne", # 'ne', 'en', 'bilingual'
        tone: str = "promotional"
    ) -> Dict[str, Any]:
        """Generate full engaging social media post caption with hashtags, emojis, and relevant image."""
        default_images = [
            "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=800&q=80",
            "https://images.unsplash.com/photo-1607082348824-0a96f2a4b9da?w=800&q=80",
            "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=800&q=80",
            "https://images.unsplash.com/photo-1526170375885-4d8ecf77b99f?w=800&q=80",
            "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=800&q=80"
        ]
        import random
        selected_img = random.choice(default_images)

        if not self._client:
            # High quality local fallback template
            if language == "ne":
                post_text = f"🎉 {topic or 'नयाँ सामानहरू विशेष छुटमा उपलब्ध छन्!'} 🛍️\n\nउच्च गुणस्तरका उत्कृष्ट सामानहरू अब नेपालभर होम डेलिभरीका साथ! आजै अर्डर गरी विशेष छुटको फाइदा लिनुहोस्।\n\n📞 सम्पर्क: इनबक्स (DM) गर्नुहोस् वा कमेन्ट गर्नुहोस्!\n\n#PyLoom #OnlineShoppingNepal #ExclusiveOffer #NepalDeals"
            elif language == "bilingual":
                post_text = f"✨ Special Announcement / विशेष जानकारी! ✨\n\n{topic or 'Exciting new arrivals are here at unbeatable prices!'}\nनयाँ सामानहरू आइपुगेका छन्! नेपालभर डेलिभरी सुविधा उपलब्ध छ।\n\n👉 Comment 'INTERESTED' or DM us for order details!\n#PyLoom #DealsNepal #SpecialOffer"
            else:
                post_text = f"🚀 {topic or 'Elevate your lifestyle with our premium collection!'} 🌟\n\nTop quality, reliable performance, and express delivery nationwide. Don't miss out on this limited-time offer!\n\n💬 Drop a comment below or send us a DM to order today!\n\n#PyLoom #QualityFirst #ShopNow #Trending"
            return {
                "message": post_text,
                "media_url": selected_img,
                "source": "smart_local_template"
            }

        prompt = f"""
Create an engaging, viral-ready Facebook Page post for a business page.
Brand Context: {brand_context or 'PyLoom client commercial business'}
Post Topic / Theme: {topic or 'Exciting product showcase and customer appreciation'}
Language: {'Nepali (Devanagari script)' if language == 'ne' else 'English' if language == 'en' else 'Bilingual (Nepali and English)'}
Tone: {tone}

Include:
- Catchy hook with emojis
- Value proposition or interesting message
- Clear Call to Action (CTA) encouraging users to comment or send a message
- 3 to 5 relevant hashtags

Format: Output pure text for the post caption.
"""
        try:
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            return {
                "message": response.text.strip(),
                "media_url": selected_img,
                "source": "gemini_api"
            }
        except Exception as err:
            print(f"Gemini post generation failed: {err}")
            return {
                "message": f"🎉 {topic or 'विशेष अफर!'} \n\nथप जानकारीको लागि हामीलाई कमेन्ट वा इनबक्स गर्नुहोस्। #PyLoom",
                "media_url": selected_img,
                "source": "fallback"
            }

gemini_service = GeminiService()
