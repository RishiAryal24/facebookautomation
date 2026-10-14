import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base

def utcnow():
    return datetime.now(timezone.utc)

class UserRole(str, enum.Enum):
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

class FacebookPage(Base):
    __tablename__ = "facebook_pages"
    
    id = Column(Integer, primary_key=True, index=True)
    meta_page_id = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    category = Column(String(100), default="Business Page")
    picture_url = Column(Text, nullable=True)
    access_token_enc = Column(Text, nullable=True)
    is_connected = Column(Boolean, default=True)
    
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
    status = Column(String(50), default="published") # draft, scheduled, published, failed
    scheduled_for = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    
    page = relationship("FacebookPage", back_populates="posts")
    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan")

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
