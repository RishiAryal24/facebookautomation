from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Optional, List, Dict, Any
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field, field_validator
from app.config import settings
from app.models.entities import UserRole, CommentStatus, ActionStatus

# Auth
class Token(BaseModel):
    access_token: str
    token_type: str
    user_role: str
    user_email: str
    expires_in: int

class TokenData(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None

class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    role: UserRole = UserRole.OPERATOR

class UserCreate(UserBase):
    password: str = Field(min_length=12, max_length=72)

    @field_validator("password")
    @classmethod
    def validate_password_bytes(cls, password: str) -> str:
        if len(password.encode("utf-8")) > 72:
            raise ValueError("Password must be no more than 72 UTF-8 bytes")
        return password

class UserRead(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)

    @field_validator("password")
    @classmethod
    def validate_password_bytes(cls, password: str) -> str:
        if len(password.encode("utf-8")) > 72:
            raise ValueError("Password must be no more than 72 UTF-8 bytes")
        return password

# Facebook Page
class FacebookPageBase(BaseModel):
    meta_page_id: str
    name: str
    category: Optional[str] = "Business Page"
    picture_url: Optional[str] = None
    timezone: str = settings.DEFAULT_TIMEZONE
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
    daily_posts_target: int = 1
    post_auto_publish: bool = False
    posting_schedule_times: str = "10:00,18:00"
    post_topics_prompt: Optional[str] = "Product highlights, special discounts, helpful tips, and engagement questions."
    posts_created_today: int = 0

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, timezone_name: str) -> str:
        try:
            ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Timezone must be a valid IANA timezone") from exc
        return timezone_name

    @field_validator("operating_hours_start", "operating_hours_end")
    @classmethod
    def validate_operating_hours(cls, value: str) -> str:
        try:
            datetime.strptime(value, "%H:%M")
        except ValueError as exc:
            raise ValueError("Operating hours must use HH:MM format") from exc
        return value

class FacebookPageCreate(FacebookPageBase):
    access_token: str = Field(min_length=1)
    user_access_token: Optional[str] = Field(default=None, min_length=1)

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
    daily_posts_target: Optional[int] = None
    post_auto_publish: Optional[bool] = None
    posting_schedule_times: Optional[str] = None
    post_topics_prompt: Optional[str] = None
    access_token: Optional[str] = None
    user_access_token: Optional[str] = Field(default=None, min_length=1)
    timezone: Optional[str] = None

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, timezone_name: Optional[str]) -> Optional[str]:
        if timezone_name is not None:
            try:
                ZoneInfo(timezone_name)
            except ZoneInfoNotFoundError as exc:
                raise ValueError("Timezone must be a valid IANA timezone") from exc
        return timezone_name

    @field_validator("operating_hours_start", "operating_hours_end")
    @classmethod
    def validate_operating_hours(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            try:
                datetime.strptime(value, "%H:%M")
            except ValueError as exc:
                raise ValueError("Operating hours must use HH:MM format") from exc
        return value

class FacebookPageRead(FacebookPageBase):
    id: int
    is_connected: bool
    token_status: str
    token_expires_at: Optional[datetime] = None
    meta_app_id: Optional[str] = None
    last_validated_at: Optional[datetime] = None
    granted_permissions: Optional[List[str]] = None
    page_tasks: Optional[List[str]] = None
    total_comments_replied: int
    total_likes_given: int
    last_synced_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

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
    is_ai_generated: bool = False
    generation_source: Optional[str] = None
    status: str = "published"
    scheduled_for: Optional[datetime] = None
    topic: Optional[str] = None
    content_category: Optional[str] = None
    content_language: Optional[str] = None
    approved_at: Optional[datetime] = None
    approved_by_user_id: Optional[int] = None
    rejection_reason: Optional[str] = None
    created_at: datetime

    @computed_field
    @property
    def is_simulated(self) -> bool:
        return "_post_" in self.meta_post_id

    @field_validator("scheduled_for", mode="before")
    @classmethod
    def serialize_schedule_as_utc(cls, value: Optional[datetime]) -> Optional[datetime]:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    model_config = ConfigDict(from_attributes=True)

class PostDraftGenerateRequest(BaseModel):
    page_id: int
    topic: Optional[str] = None
    language: Optional[str] = "ne" # 'ne', 'en', 'bilingual'
    tone: Optional[str] = "promotional" # promotional, tips, festive, engagement
    include_image: bool = True
    category: Optional[str] = None
    request_id: Optional[str] = Field(default=None, min_length=1, max_length=120)

    @field_validator("language")
    @classmethod
    def validate_content_language(cls, language: Optional[str]) -> Optional[str]:
        if language is not None and language not in {"en", "ne", "bilingual"}:
            raise ValueError("Language must be en, ne, or bilingual")
        return language


class ContentAutomationConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    frequency: Optional[str] = None
    generation_time: Optional[str] = None
    timezone: Optional[str] = None
    posts_per_cycle: Optional[int] = Field(default=None, ge=1, le=5)
    languages: Optional[List[str]] = None
    tone: Optional[str] = Field(default=None, min_length=1, max_length=80)
    category_mode: Optional[str] = None
    categories: Optional[List[str]] = None
    approval_required: Optional[bool] = None
    brand_context: Optional[str] = Field(default=None, min_length=1, max_length=10000)

    @field_validator("frequency")
    @classmethod
    def validate_frequency(cls, frequency: Optional[str]) -> Optional[str]:
        if frequency is not None and frequency not in {"daily"}:
            raise ValueError("Only daily content generation is currently supported")
        return frequency

    @field_validator("generation_time")
    @classmethod
    def validate_generation_time(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            try:
                datetime.strptime(value, "%H:%M")
            except ValueError as exc:
                raise ValueError("Generation time must use HH:MM format") from exc
        return value

    @field_validator("timezone")
    @classmethod
    def validate_generation_timezone(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            try:
                ZoneInfo(value)
            except ZoneInfoNotFoundError as exc:
                raise ValueError("Timezone must be a valid IANA timezone") from exc
        return value

    @field_validator("languages")
    @classmethod
    def validate_generation_languages(cls, values: Optional[List[str]]) -> Optional[List[str]]:
        if values is not None:
            if not values or any(value not in {"en", "ne", "bilingual"} for value in values):
                raise ValueError("Languages must contain en, ne, and/or bilingual")
            return list(dict.fromkeys(values))
        return values

    @field_validator("category_mode")
    @classmethod
    def validate_category_mode(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value not in {"rotating", "custom"}:
            raise ValueError("Category mode must be rotating or custom")
        return value

    @field_validator("categories")
    @classmethod
    def validate_categories(cls, values: Optional[List[str]]) -> Optional[List[str]]:
        if values is not None:
            cleaned = list(dict.fromkeys(value.strip() for value in values if value.strip()))
            if not cleaned or len(cleaned) > 20:
                raise ValueError("Provide between 1 and 20 non-empty content categories")
            return cleaned
        return values


class ContentAutomationConfigRead(BaseModel):
    id: int
    page_id: int
    enabled: bool
    frequency: str
    generation_time: str
    timezone: str
    posts_per_cycle: int
    languages: List[str]
    tone: str
    category_mode: str
    categories: List[str]
    approval_required: bool
    auto_publish_enabled: bool
    brand_context: str
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PostScheduleRequest(BaseModel):
    scheduled_for: datetime

    @field_validator("scheduled_for")
    @classmethod
    def require_future_timezone_aware_schedule(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Scheduled time must include a timezone")
        return value


class PostRejectRequest(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=2000)


class PostContentVersionRead(BaseModel):
    id: int
    post_id: int
    version: int
    event_type: str
    message: str
    actor_user_id: Optional[int] = None
    reason: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ContentGenerationRunRead(BaseModel):
    id: int
    page_id: int
    run_key: str
    source: str
    status: str
    topic: Optional[str] = None
    content_category: Optional[str] = None
    error_message: Optional[str] = None
    attempt_count: int
    post_id: Optional[int] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

class PostPublishRequest(BaseModel):
    edited_message: Optional[str] = None
    media_url: Optional[str] = None
    confirm_publish: bool = False
    model_config = ConfigDict(from_attributes=True)

    @field_validator("edited_message")
    @classmethod
    def validate_edited_message(cls, message: Optional[str]) -> Optional[str]:
        if message is not None and not message.strip():
            raise ValueError("Edited message cannot be empty")
        return message

class PostDraftUpdate(BaseModel):
    message: str = Field(min_length=1, max_length=63206)
    media_url: Optional[str] = None

    @field_validator("message")
    @classmethod
    def validate_message(cls, message: str) -> str:
        if not message.strip():
            raise ValueError("Draft message cannot be empty")
        return message

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
    ai_generation_source: Optional[str] = None
    is_simulated: bool = False
    final_reply: Optional[str] = None
    status: CommentStatus
    is_liked: bool
    published_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime
    post_message: Optional[str] = None
    page_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

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

    model_config = ConfigDict(from_attributes=True)

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
    model_config = ConfigDict(from_attributes=True)

# Action Logs & Dashboard
class ActionLogRead(BaseModel):
    id: int
    page_id: Optional[int] = None
    action_type: str
    status: ActionStatus
    details: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class DashboardMetrics(BaseModel):
    total_pages_connected: int
    total_posts_monitored: int
    total_comments_received: int
    pending_approvals_count: int
    published_replies_count: int
    total_likes_given: int
    automation_active: bool
    recent_activity: List[ActionLogRead] = []

class AdAccountRead(BaseModel):
    account_id: Optional[str] = None
    name: Optional[str] = None
    currency: str
    configured: bool
    connected: bool
    simulated: bool
    max_daily_budget: Decimal
    message: Optional[str] = None

class AdCampaignRead(BaseModel):
    meta_campaign_id: str
    ad_account_id: str
    name: str
    objective: Optional[str] = None
    status: str
    effective_status: Optional[str] = None
    daily_budget: Optional[Decimal] = None
    lifetime_budget: Optional[Decimal] = None
    currency: str
    today_spend: Decimal
    impressions: int
    clicks: int
    delivery_date: Optional[date] = None
    last_synced_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class AdBudgetUpdate(BaseModel):
    daily_budget: Decimal = Field(gt=0, le=Decimal("5.00"), max_digits=4, decimal_places=2)

class AdCampaignStatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, status: str) -> str:
        normalized = status.upper()
        if normalized not in {"ACTIVE", "PAUSED"}:
            raise ValueError("Campaign status must be ACTIVE or PAUSED")
        return normalized
