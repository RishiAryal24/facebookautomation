import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from app.config import settings
from app.core.security import decrypt_token

class MetaGraphClient:
    def __init__(self):
        self.base_url = f"https://graph.facebook.com/{settings.META_GRAPH_VERSION}"
        self.app_id = settings.META_APP_ID
        self.app_secret = settings.META_APP_SECRET

    async def get_page_info(self, page_id: str, access_token: str) -> Dict[str, Any]:
        """Fetch Page profile details."""
        if not access_token or access_token.startswith("mock_"):
            return {
                "id": page_id,
                "name": "PyLoom Official Store (Simulated)",
                "category": "E-Commerce & Retail",
                "picture": {"data": {"url": "https://images.unsplash.com/photo-1522071820081-009f0129c71c?w=128&q=80"}}
            }
        
        url = f"{self.base_url}/{page_id}"
        params = {
            "fields": "id,name,category,picture.type(large)",
            "access_token": access_token
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()

    async def fetch_page_posts(self, page_id: str, access_token: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Fetch latest posts from Facebook Page feed."""
        if not access_token or access_token.startswith("mock_"):
            return [
                {
                    "id": f"{page_id}_post_101",
                    "message": "🎉 Big Festival Sale is LIVE! Enjoy up to 40% OFF on all items! Drop a comment to grab your exclusive discount voucher. Offer valid till Sunday! 🛍️✨",
                    "permalink_url": "https://facebook.com/posts/101",
                    "full_picture": "https://images.unsplash.com/photo-1607082348824-0a96f2a4b9da?w=600&q=80",
                    "created_time": datetime.now(timezone.utc).isoformat(),
                    "likes": {"summary": {"total_count": 84}},
                    "comments": {"summary": {"total_count": 12}}
                },
                {
                    "id": f"{page_id}_post_102",
                    "message": "नयाँ सामानहरू आइपुगेका छन्! उच्च गुणस्तर र सुपथ मूल्यमा नेपालभर होम डेलिभरी उपलब्ध छ। अर्डर गर्न कमेन्ट गर्नुहोस् वा इनबक्स गर्नुहोस्। 🇳🇵📦",
                    "permalink_url": "https://facebook.com/posts/102",
                    "full_picture": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&q=80",
                    "created_time": datetime.now(timezone.utc).isoformat(),
                    "likes": {"summary": {"total_count": 142}},
                    "comments": {"summary": {"total_count": 27}}
                }
            ]

        url = f"{self.base_url}/{page_id}/feed"
        params = {
            "fields": "id,message,permalink_url,full_picture,created_time,likes.summary(true),comments.summary(true)",
            "limit": limit,
            "access_token": access_token
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", [])

    async def fetch_post_comments(self, post_id: str, access_token: str, limit: int = 25) -> List[Dict[str, Any]]:
        """Fetch comments for a given Facebook post."""
        if not access_token or access_token.startswith("mock_"):
            return []

        url = f"{self.base_url}/{post_id}/comments"
        params = {
            "fields": "id,from,message,created_time,like_count",
            "limit": limit,
            "access_token": access_token
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", [])

    async def publish_comment_reply(self, parent_comment_id: str, message: str, access_token: str) -> Dict[str, Any]:
        """Publish a reply to a Facebook comment using Page Token."""
        if not access_token or access_token.startswith("mock_"):
            return {
                "id": f"simulated_reply_{parent_comment_id}_{int(datetime.now().timestamp())}",
                "status": "success",
                "simulated": True
            }

        url = f"{self.base_url}/{parent_comment_id}/comments"
        data = {
            "message": message,
            "access_token": access_token
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, data=data)
            resp.raise_for_status()
            return resp.json()

    async def like_comment(self, comment_id: str, access_token: str) -> Dict[str, Any]:
        """Send a Like reaction to a comment as the Page."""
        if not access_token or access_token.startswith("mock_"):
            return {"success": True, "simulated": True}

        url = f"{self.base_url}/{comment_id}/likes"
        data = {"access_token": access_token}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, data=data)
            resp.raise_for_status()
            return resp.json()

meta_client = MetaGraphClient()
