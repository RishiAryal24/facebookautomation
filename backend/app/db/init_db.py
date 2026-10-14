from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import engine, Base, AsyncSessionLocal
from app.core.security import get_password_hash, encrypt_token
from app.models.entities import (
    User, UserRole, FacebookPage, Post, Comment, CommentStatus,
    RestrictedKeyword, AutomationRule, ActionLog, ActionStatus
)

async def init_models():
    """Create all tables in the database."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def seed_data():
    """Seed initial administrator, restricted keywords, demo page, and sample bilingual comments."""
    async with AsyncSessionLocal() as db:
        # 1. Admin user
        res_user = await db.execute(select(User).where(User.email == "admin@pyloom.com"))
        admin_user = res_user.scalar_one_or_none()
        if not admin_user:
            admin_user = User(
                email="admin@pyloom.com",
                hashed_password=get_password_hash("admin123"),
                full_name="PyLoom Administrator",
                role=UserRole.ADMIN
            )
            db.add(admin_user)

        # 2. Restricted Keywords
        default_keywords = [
            ("scam", "crisis", "flag_for_review"),
            ("fake", "crisis", "flag_for_review"),
            ("refund", "complaint", "flag_for_review"),
            ("terrible service", "complaint", "flag_for_review"),
            ("धोका", "crisis", "flag_for_review"),
            ("ठग", "crisis", "flag_for_review"),
            ("नक्कली", "crisis", "flag_for_review"),
            ("छल", "crisis", "flag_for_review")
        ]
        for kw, cat, act in default_keywords:
            res_kw = await db.execute(select(RestrictedKeyword).where(RestrictedKeyword.keyword == kw))
            if not res_kw.scalar_one_or_none():
                db.add(RestrictedKeyword(keyword=kw, category=cat, action=act))

        # 3. Demo Facebook Page
        res_page = await db.execute(select(FacebookPage).where(FacebookPage.meta_page_id == "pyloom_page_001"))
        page = res_page.scalar_one_or_none()
        if not page:
            page = FacebookPage(
                meta_page_id="pyloom_page_001",
                name="PyLoom Digital Store",
                category="E-Commerce & Digital Marketing",
                picture_url="https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=128&q=80",
                access_token_enc=encrypt_token("mock_page_token_pyloom_2026"),
                is_connected=True,
                automation_enabled=True,
                auto_approve_enabled=False,  # Defaults to Approval Queue for human safety
                auto_like_enabled=True,
                default_language="bilingual",
                response_tone="friendly",
                brand_context="PyLoom Digital Store sells premium tech gadgets, accessories, and digital solutions with nationwide delivery in Nepal.",
                operating_hours_start="08:00",
                operating_hours_end="22:00",
                max_actions_per_hour=30,
                total_comments_replied=14,
                total_likes_given=14,
                last_synced_at=datetime.now(timezone.utc)
            )
            db.add(page)
            await db.flush()

            # 4. Posts for this Page
            post1 = Post(
                meta_post_id="post_festive_deal_101",
                page_id=page.id,
                message="🎉 नेपालीहरूको महान चाडपर्वको अवसरमा विशेष छुट! हाम्रा सबै डिजिटल ग्याजेटहरूमा ४०% सम्मको भारी छुट। नेपालभर होम डेलिभरी उपलब्ध छ। तुरुन्त अर्डर गर्न तल कमेन्ट गर्नुहोस् वा इनबक्स गर्नुहोस्! 🇳🇵🎁",
                permalink_url="https://facebook.com/pyloom/posts/101",
                media_url="https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&q=80",
                like_count=128,
                comment_count=4,
                is_monitored=True
            )
            post2 = Post(
                meta_post_id="post_english_launch_102",
                page_id=page.id,
                message="🚀 Launching our all-new Wireless Noise-Cancelling Earbuds Pro! Crystal clear sound, 36hr battery backup, and IPX7 water resistance. Comment 'PRICE' to get an instant exclusive voucher code in your DM! 🎧⚡",
                permalink_url="https://facebook.com/pyloom/posts/102",
                media_url="https://images.unsplash.com/photo-1590658268037-6bf12165a8df?w=600&q=80",
                like_count=94,
                comment_count=3,
                is_monitored=True
            )
            db.add(post1)
            db.add(post2)
            await db.flush()

            # 5. Seed Bilingual Sample Comments in the Approval Queue & Published
            sample_comments = [
                Comment(
                    meta_comment_id="cmt_nep_001",
                    post_id=post1.id,
                    page_id=page.id,
                    sender_name="Sunil Adhikari",
                    message="यो ग्याजेटको मूल्य कति पर्छ होला? पोखरामा डेलिभरी हुन्छ कि नाइँ?",
                    detected_language="ne",
                    sentiment="question",
                    ai_draft_reply="नमस्ते सुनिल जी! हजुरको रुचिको लागि धन्यवाद। पोखरामा २ दिनभित्रै होम डेलिभरी उपलब्ध छ। मूल्य तथा अर्डर प्रक्रियाबारे विस्तृत जानकारी हजुरको इनबक्स (DM) मा पठाएका छौँ, कृपया चेक गर्नुहोला। 🙏✨",
                    status=CommentStatus.PENDING_APPROVAL
                ),
                Comment(
                    meta_comment_id="cmt_eng_002",
                    post_id=post2.id,
                    page_id=page.id,
                    sender_name="Aarav Sharma",
                    message="PRICE please! Does it come with warranty?",
                    detected_language="en",
                    sentiment="question",
                    ai_draft_reply="Hello Aarav! Thank you for your interest. Yes, the Earbuds Pro come with a 1-Year Official Replacement Warranty! We've just sent full pricing and your exclusive voucher code to your inbox (DM). Please check! 😊🎧",
                    status=CommentStatus.PENDING_APPROVAL
                ),
                Comment(
                    meta_comment_id="cmt_nep_003",
                    post_id=post1.id,
                    page_id=page.id,
                    sender_name="Pooja Shrestha",
                    message="धेरै राम्रो अफर रहेछ, सामानको क्वालिटी एकदमै राम्रो लाग्यो।",
                    detected_language="ne",
                    sentiment="positive",
                    ai_draft_reply="धेरै धेरै धन्यवाद पूजा जी! हजुरको सकारात्मक प्रतिक्रियाले हामीलाई अझ राम्रो सेवा दिन प्रेरणा दिएको छ। सधैँ साथ दिनुहोला! ❤️🙏",
                    final_reply="धेरै धेरै धन्यवाद पूजा जी! हजुरको सकारात्मक प्रतिक्रियाले हामीलाई अझ राम्रो सेवा दिन प्रेरणा दिएको छ। सधैँ साथ दिनुहोला! ❤️🙏",
                    status=CommentStatus.PUBLISHED,
                    is_liked=True,
                    published_at=datetime.now(timezone.utc)
                ),
                Comment(
                    meta_comment_id="cmt_flagged_004",
                    post_id=post1.id,
                    page_id=page.id,
                    sender_name="Anonymous User",
                    message="I want refund for my previous order, delivery was delayed.",
                    detected_language="en",
                    sentiment="negative",
                    ai_draft_reply="Hello, we are truly sorry for the inconvenience caused by the delivery delay. Our support lead has been notified and will assist you immediately via DM.",
                    status=CommentStatus.PENDING_APPROVAL,
                    error_message="Contains restricted keyword: 'refund' (complaint)"
                )
            ]
            for c in sample_comments:
                db.add(c)

            # Sample Action Log
            log1 = ActionLog(
                page_id=page.id,
                action_type="comment_reply",
                status=ActionStatus.SUCCESS,
                details={"comment_id": "cmt_nep_003", "sender": "Pooja Shrestha", "language": "ne"}
            )
            db.add(log1)

        await db.commit()
