from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr
from app.models.entities import UserRole, CommentStatus, ActionStatus

# Auth
class Token(BaseModel):
    access_token: str
    token_type: str
    user_role: str
    user_email: str

class TokenData(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None

class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    role: UserRole = UserRole.OPERATOR
    is_active: bool = True

class UserCreate(UserBase):
    password: str

class UserRead(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class LoginRequest(BaseModel):
    email: str
    password: str

# Facebook Page
class FacebookPageBase(BaseModel):
    meta_page_id: str
    name: str
    category: Optional[str] = "Business Page"
    picture_url: Optional[str] = None
    automation_enabled: bool = True
    auto_approve_enabled: bool = False
    auto_like_enabled: bool = True
    default_language: str = "bilingual"
    response_tone: str = "friendly"
    brand_context: Optional[str] = "PyLoom client business page."
    operating_hours_start: str = "08:00"
    operating_hours_end: str = "22:00"
    max_actions_per_hour: int = 30
    cooldown_seconds: int = 15

class FacebookPageCreate(FacebookPageBase):
    access_token: Optional[str] = None

class FacebookPageUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    automation_enabled: Optional[bool] = None
    auto_approve_enabled: Optional[bool] = None
    auto_like_enabled: Optional[bool] = None
    default_language: Optional[str] = None
    response_tone: Optional[str] = None
    brand_context: Optional[str] = None
    operating_hours_start: Optional[str] = None
    operating_hours_end: Optional[str] = None
    max_actions_per_hour: Optional[int] = None
    cooldown_seconds: Optional[int] = None
    access_token: Optional[str] = None

class FacebookPageRead(FacebookPageBase):
    id: int
    is_connected: bool
    total_comments_replied: int
    total_likes_given: int
    last_synced_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True

# Post
class PostRead(BaseModel):
    id: int
    meta_post_id: str
    page_id: int
    message: Optional[str] = None
    permalink_url: Optional[str] = None
    media_url: Optional[str] = None
    published_at: Optional[datetime] = None
    like_count: int
    comment_count: int
    is_monitored: bool
    created_at: datetime

    class Config:
        from_attributes = True

# Comment
class CommentRead(BaseModel):
    id: int
    meta_comment_id: str
    post_id: int
    page_id: int
    sender_id: Optional[str] = None
    sender_name: str
    message: str
    detected_language: str
    sentiment: str
    ai_draft_reply: Optional[str] = None
    final_reply: Optional[str] = None
    status: CommentStatus
    is_liked: bool
    published_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime
    post_message: Optional[str] = None
    page_name: Optional[str] = None

    class Config:
        from_attributes = True

class CommentApproveRequest(BaseModel):
    edited_reply: Optional[str] = None
    also_like: bool = True

class CommentRejectRequest(BaseModel):
    reason: Optional[str] = None

class CommentRegenerateRequest(BaseModel):
    tone: Optional[str] = None # friendly, professional, support, promotional
    target_language: Optional[str] = None # en, ne, bilingual
    custom_instructions: Optional[str] = None

class SimulateCommentRequest(BaseModel):
    page_id: int
    post_id: Optional[int] = None
    sender_name: str = "Test Customer"
    message: str
    language_hint: Optional[str] = "ne" # 'en' or 'ne'

# Rules & Keywords
class RestrictedKeywordCreate(BaseModel):
    keyword: str
    category: str = "profanity"
    action: str = "flag_for_review"

class RestrictedKeywordRead(BaseModel):
    id: int
    keyword: str
    category: str
    action: str
    created_at: datetime

    class Config:
        from_attributes = True

class AutomationRuleCreate(BaseModel):
    page_id: Optional[int] = None
    name: str
    rule_type: str = "keyword_auto_reply"
    trigger_keyword: Optional[str] = None
    target_language: str = "auto"
    response_template: Optional[str] = None
    is_active: bool = True

class AutomationRuleRead(AutomationRuleCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# Action Logs & Dashboard
class ActionLogRead(BaseModel):
    id: int
    page_id: Optional[int] = None
    action_type: str
    status: ActionStatus
    details: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class DashboardMetrics(BaseModel):
    total_pages_connected: int
    total_posts_monitored: int
    total_comments_received: int
    pending_approvals_count: int
    published_replies_count: int
    total_likes_given: int
    automation_active: bool
    recent_activity: List[ActionLogRead] = []
