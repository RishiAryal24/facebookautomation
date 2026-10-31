import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Date,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    Enum,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from app.core.database import Base

def utcnow():
    return datetime.now(timezone.utc)

class UserRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    COMPANY_ADMIN = "company_admin"
    # Kept for existing databases created before role names were expanded.
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"

class CommentStatus(str, enum.Enum):
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    PUBLISHED = "published"
    REJECTED = "rejected"
    FAILED = "failed"

class ActionStatus(str, enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    role = Column(Enum(UserRole), default=UserRole.OPERATOR, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)

    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")

class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    refresh_token_hash = Column(String(64), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    last_used_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="sessions")

class FacebookPage(Base):
    __tablename__ = "facebook_pages"
    
    id = Column(Integer, primary_key=True, index=True)
    meta_page_id = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    category = Column(String(100), default="Business Page")
    picture_url = Column(Text, nullable=True)
    access_token_enc = Column(Text, nullable=True)
    token_status = Column(String(30), default="not_configured", nullable=False)
    token_expires_at = Column(DateTime, nullable=True)
    meta_app_id = Column(String(100), nullable=True)
    last_validated_at = Column(DateTime, nullable=True)
    granted_permissions = Column(JSON, nullable=True)
    page_tasks = Column(JSON, nullable=True)
    is_connected = Column(Boolean, default=True)
    timezone = Column(String(64), default="Asia/Kathmandu", nullable=False)
    
    # Automation Configuration
    automation_enabled = Column(Boolean, default=True)  # Global toggle for page
    auto_approve_enabled = Column(Boolean, default=False) # False = approval queue, True = full auto-pilot
    auto_like_enabled = Column(Boolean, default=True)   # Policy-compliant like on customer comment
    default_language = Column(String(20), default="bilingual")  # bilingual, en, ne
    response_tone = Column(String(50), default="friendly")  # friendly, professional, support, promotional
    brand_context = Column(Text, default="PyLoom client business page. Be polite, prompt, and helpful.")
    
    # Guardrails
    operating_hours_start = Column(String(5), default="08:00")  # HH:MM
    operating_hours_end = Column(String(5), default="22:00")    # HH:MM
    max_actions_per_hour = Column(Integer, default=30)
    cooldown_seconds = Column(Integer, default=15)
    
    # Daily Automated Post Generation
    daily_posts_target = Column(Integer, default=1)
    post_auto_publish = Column(Boolean, default=False) # False = draft queue, True = auto-publish
    posting_schedule_times = Column(String(255), default="10:00,18:00")
    post_topics_prompt = Column(Text, default="Product highlights, special discounts, helpful tips, and engagement questions.")
    posts_created_today = Column(Integer, default=0)
    posts_counter_reset_on = Column(Date, nullable=True)

    # Metrics
    total_comments_replied = Column(Integer, default=0)
    total_likes_given = Column(Integer, default=0)
    last_synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    
    # Relationships
    posts = relationship("Post", back_populates="page", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="page", cascade="all, delete-orphan")
    action_logs = relationship("ActionLog", back_populates="page", cascade="all, delete-orphan")
    rules = relationship("AutomationRule", back_populates="page", cascade="all, delete-orphan")
    content_generation_config = relationship(
        "ContentGenerationConfig",
        back_populates="page",
        uselist=False,
        cascade="all, delete-orphan",
    )
    content_generation_runs = relationship(
        "ContentGenerationRun",
        back_populates="page",
        cascade="all, delete-orphan",
    )

class Post(Base):
    __tablename__ = "posts"
    
    id = Column(Integer, primary_key=True, index=True)
    meta_post_id = Column(String(150), unique=True, index=True, nullable=False)
    page_id = Column(Integer, ForeignKey("facebook_pages.id"), nullable=False)
    message = Column(Text, nullable=True)
    permalink_url = Column(Text, nullable=True)
    media_url = Column(Text, nullable=True)
    published_at = Column(DateTime, nullable=True)
    like_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    is_monitored = Column(Boolean, default=True)
    is_ai_generated = Column(Boolean, default=False)
    generation_source = Column(String(30), nullable=True)
    status = Column(String(50), default="published") # draft, scheduled, published, failed
    scheduled_for = Column(DateTime, nullable=True)
    topic = Column(Text, nullable=True)
    content_category = Column(String(80), nullable=True)
    content_language = Column(String(30), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    approved_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    
    page = relationship("FacebookPage", back_populates="posts")
    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan")
    content_versions = relationship(
        "PostContentVersion",
        back_populates="post",
        cascade="all, delete-orphan",
        order_by="PostContentVersion.version",
    )


class ContentGenerationConfig(Base):
    __tablename__ = "content_generation_configs"

    id = Column(Integer, primary_key=True, index=True)
    page_id = Column(Integer, ForeignKey("facebook_pages.id", ondelete="CASCADE"), unique=True, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    frequency = Column(String(20), default="daily", nullable=False)
    generation_time = Column(String(5), default="09:00", nullable=False)
    timezone = Column(String(64), default="Asia/Kathmandu", nullable=False)
    posts_per_cycle = Column(Integer, default=1, nullable=False)
    languages = Column(JSON, default=lambda: ["en", "ne"], nullable=False)
    tone = Column(String(80), default="professional and engaging", nullable=False)
    category_mode = Column(String(20), default="rotating", nullable=False)
    categories = Column(
        JSON,
        default=lambda: [
            "Company promotions",
            "Software development",
            "AI and automation",
            "Educational technology",
            "Technology trends",
            "Product highlights",
            "Customer engagement",
            "Festivals and special occasions",
        ],
        nullable=False,
    )
    approval_required = Column(Boolean, default=True, nullable=False)
    auto_publish_enabled = Column(Boolean, default=False, nullable=False)
    brand_context = Column(
        Text,
        default=(
            "PyLoom Technologies Pvt. Ltd. Tagline: Weaving Innovation Beyond Expectations. "
            "Services: AI-powered software development, business automation, custom software "
            "development, data analytics, hospital management systems, and e-commerce solutions."
        ),
        nullable=False,
    )
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    page = relationship("FacebookPage", back_populates="content_generation_config")


class ContentGenerationRun(Base):
    __tablename__ = "content_generation_runs"
    __table_args__ = (
        UniqueConstraint("page_id", "run_key", name="uq_content_generation_page_run"),
    )

    id = Column(Integer, primary_key=True, index=True)
    page_id = Column(Integer, ForeignKey("facebook_pages.id", ondelete="CASCADE"), nullable=False)
    run_key = Column(String(120), nullable=False)
    source = Column(String(20), nullable=False)
    status = Column(String(20), default="in_progress", nullable=False)
    topic = Column(Text, nullable=True)
    content_category = Column(String(80), nullable=True)
    error_message = Column(Text, nullable=True)
    attempt_count = Column(Integer, default=1, nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="SET NULL"), nullable=True)
    started_at = Column(DateTime, default=utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    page = relationship("FacebookPage", back_populates="content_generation_runs")
    post = relationship("Post")


class PostContentVersion(Base):
    __tablename__ = "post_content_versions"
    __table_args__ = (
        UniqueConstraint("post_id", "version", name="uq_post_content_version"),
    )

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False)
    event_type = Column(String(30), nullable=False)
    message = Column(Text, nullable=False)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    post = relationship("Post", back_populates="content_versions")
    actor = relationship("User")

class Comment(Base):
    __tablename__ = "comments"
    
    id = Column(Integer, primary_key=True, index=True)
    meta_comment_id = Column(String(150), unique=True, index=True, nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    page_id = Column(Integer, ForeignKey("facebook_pages.id"), nullable=False)
    
    sender_id = Column(String(100), nullable=True)
    sender_name = Column(String(255), default="Facebook User")
    message = Column(Text, nullable=False)
    
    # AI Analysis & Draft
    detected_language = Column(String(20), default="en") # en, ne, mixed
    sentiment = Column(String(30), default="neutral")    # positive, neutral, negative, question
    ai_draft_reply = Column(Text, nullable=True)
    ai_generation_source = Column(String(30), nullable=True)
    is_simulated = Column(Boolean, default=False, nullable=False)
    final_reply = Column(Text, nullable=True)
    status = Column(Enum(CommentStatus), default=CommentStatus.PENDING_APPROVAL, nullable=False)
    
    is_liked = Column(Boolean, default=False)
    published_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    
    post = relationship("Post", back_populates="comments")
    page = relationship("FacebookPage", back_populates="comments")

class RestrictedKeyword(Base):
    __tablename__ = "restricted_keywords"
    
    id = Column(Integer, primary_key=True, index=True)
    keyword = Column(String(100), unique=True, index=True, nullable=False)
    category = Column(String(50), default="profanity") # profanity, competitor, crisis, complaint
    action = Column(String(50), default="flag_for_review") # flag_for_review, block_auto_reply
    created_at = Column(DateTime, default=utcnow)

class AutomationRule(Base):
    __tablename__ = "automation_rules"
    
    id = Column(Integer, primary_key=True, index=True)
    page_id = Column(Integer, ForeignKey("facebook_pages.id"), nullable=True) # Null = applies to all pages
    name = Column(String(255), nullable=False)
    rule_type = Column(String(50), default="keyword_auto_reply") # keyword_auto_reply, tone_override, template
    trigger_keyword = Column(String(255), nullable=True)
    target_language = Column(String(20), default="auto") # auto, en, ne
    response_template = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)
    
    page = relationship("FacebookPage", back_populates="rules")

class ActionLog(Base):
    __tablename__ = "action_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    page_id = Column(Integer, ForeignKey("facebook_pages.id"), nullable=True)
    action_type = Column(String(100), nullable=False) # comment_reply, comment_like, token_refresh, sync_posts, emergency_stop
    status = Column(Enum(ActionStatus), default=ActionStatus.SUCCESS, nullable=False)
    details = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    
    page = relationship("FacebookPage", back_populates="action_logs")

class ScheduledPostRun(Base):
    __tablename__ = "scheduled_post_runs"
    __table_args__ = (
        UniqueConstraint("page_id", "scheduled_for", name="uq_scheduled_post_page_time"),
    )

    id = Column(Integer, primary_key=True, index=True)
    page_id = Column(Integer, ForeignKey("facebook_pages.id", ondelete="CASCADE"), nullable=False)
    scheduled_for = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(20), default="in_progress", nullable=False)
    attempt_count = Column(Integer, default=1, nullable=False)
    last_error = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    last_attempt_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    page = relationship("FacebookPage")
    post = relationship("Post")

class AdCampaign(Base):
    __tablename__ = "ad_campaigns"

    id = Column(Integer, primary_key=True, index=True)
    meta_campaign_id = Column(String(100), unique=True, index=True, nullable=False)
    ad_account_id = Column(String(100), index=True, nullable=False)
    name = Column(String(255), nullable=False)
    objective = Column(String(100), nullable=True)
    status = Column(String(30), nullable=False)
    effective_status = Column(String(50), nullable=True)
    daily_budget_minor = Column(Integer, nullable=True)
    lifetime_budget_minor = Column(Integer, nullable=True)
    currency = Column(String(3), nullable=False)
    spend_minor = Column(Integer, default=0, nullable=False)
    impressions = Column(Integer, default=0, nullable=False)
    clicks = Column(Integer, default=0, nullable=False)
    delivery_date = Column(Date, nullable=True)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)

class AdCampaignDailyDelivery(Base):
    __tablename__ = "ad_campaign_daily_delivery"
    __table_args__ = (
        UniqueConstraint("meta_campaign_id", "delivery_date", name="uq_ad_campaign_delivery_day"),
    )

    id = Column(Integer, primary_key=True, index=True)
    meta_campaign_id = Column(String(100), ForeignKey("ad_campaigns.meta_campaign_id", ondelete="CASCADE"), nullable=False)
    delivery_date = Column(Date, nullable=False)
    spend_minor = Column(Integer, default=0, nullable=False)
    impressions = Column(Integer, default=0, nullable=False)
    clicks = Column(Integer, default=0, nullable=False)
    actions = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    campaign = relationship("AdCampaign")
