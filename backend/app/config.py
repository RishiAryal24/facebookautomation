import os
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    PROJECT_NAME: str = "PyLoom Facebook Automation System"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Security & JWT
    SECRET_KEY: str = "pyloom-facebook-secret-key-change-in-production-2026-secure"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # Token Encryption Key for Meta credentials (Fernet key)
    # Must be 32 url-safe base64-encoded bytes
    ENCRYPTION_KEY: str = "s2bQpZ7k4n1gE8wL-5rTvX9yUz3mA6cD0eF2hJ4lNo8="
    
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./facebook_automation.db"
    
    # Gemini AI
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    
    # Meta / Facebook Graph API
    META_APP_ID: str = ""
    META_APP_SECRET: str = ""
    META_VERIFY_TOKEN: str = "pyloom_meta_webhook_verify_token_2026"
    META_GRAPH_VERSION: str = "v21.0"
    
    # Operating & Safety Defaults
    SIMULATION_MODE: bool = True  # When True, can generate simulated posts/comments for testing
    DEFAULT_OPERATING_HOURS_START: str = "08:00"
    DEFAULT_OPERATING_HOURS_END: str = "22:00"
    DEFAULT_RATE_LIMIT_PER_HOUR: int = 30
    DEFAULT_COOLDOWN_SECONDS: int = 15
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000"
    ]

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
