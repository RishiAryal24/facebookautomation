from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, model_validator
from cryptography.fernet import Fernet


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env",
        case_sensitive=True,
    )

    PROJECT_NAME: str = "PyLoom Facebook Automation System"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    
    # Security & JWT
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    AUTH_COOKIE_SECURE: bool = False
    
    # Token Encryption Key for Meta credentials (Fernet key)
    # Must be 32 url-safe base64-encoded bytes
    ENCRYPTION_KEY: str = ""

    # Optional one-time initial account provisioned during database seeding
    INITIAL_ADMIN_EMAIL: str = ""
    INITIAL_ADMIN_PASSWORD: str = ""
    
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./facebook_automation.db"
    
    # Gemini AI
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    ENABLE_LOCAL_AI_FALLBACK: bool = False
    
    # Meta / Facebook Graph API
    META_APP_ID: str = ""
    META_APP_SECRET: str = ""
    META_VERIFY_TOKEN: str = ""
    META_GRAPH_API_VERSION: str = "v26.0"
    META_AD_ACCOUNT_ID: str = ""
    META_AD_ACCESS_TOKEN: str = ""
    META_AD_CURRENCY: str = "NPR"
    META_AD_ACCOUNT_TIMEZONE: str = "Asia/Kathmandu"
    
    # Operating & Safety Defaults
    SIMULATION_MODE: bool = True  # When True, can generate simulated posts/comments for testing
    DEFAULT_OPERATING_HOURS_START: str = "08:00"
    DEFAULT_OPERATING_HOURS_END: str = "22:00"
    DEFAULT_RATE_LIMIT_PER_HOUR: int = 30
    DEFAULT_COOLDOWN_SECONDS: int = 15
    DEFAULT_TIMEZONE: str = "Asia/Kathmandu"
    SCHEDULER_MAX_ATTEMPTS: int = 3
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000"
    ]

    @model_validator(mode="after")
    def validate_security_configuration(self):
        if len(self.SECRET_KEY) < 32:
            raise ValueError("SECRET_KEY must be configured with at least 32 characters")
        try:
            Fernet(self.ENCRYPTION_KEY.encode())
        except (ValueError, TypeError):
            raise ValueError("ENCRYPTION_KEY must be a valid Fernet key")
        if not self.META_VERIFY_TOKEN:
            raise ValueError("META_VERIFY_TOKEN must be configured")
        if "*" in self.BACKEND_CORS_ORIGINS:
            raise ValueError("BACKEND_CORS_ORIGINS cannot contain wildcard origins")
        if self.AUTH_COOKIE_SECURE is False and self.ENVIRONMENT.lower() == "production":
            raise ValueError("AUTH_COOKIE_SECURE must be true in production")
        if bool(self.INITIAL_ADMIN_EMAIL) != bool(self.INITIAL_ADMIN_PASSWORD):
            raise ValueError("INITIAL_ADMIN_EMAIL and INITIAL_ADMIN_PASSWORD must be set together")
        if self.INITIAL_ADMIN_PASSWORD and len(self.INITIAL_ADMIN_PASSWORD) < 12:
            raise ValueError("INITIAL_ADMIN_PASSWORD must contain at least 12 characters")
        if len(self.INITIAL_ADMIN_PASSWORD.encode("utf-8")) > 72:
            raise ValueError("INITIAL_ADMIN_PASSWORD must not exceed 72 UTF-8 bytes")
        if self.SCHEDULER_MAX_ATTEMPTS < 1:
            raise ValueError("SCHEDULER_MAX_ATTEMPTS must be at least 1")
        return self

settings = Settings()
