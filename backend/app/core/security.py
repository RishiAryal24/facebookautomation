import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Union, Any
from jose import jwt
from passlib.context import CryptContext
from cryptography.fernet import Fernet
from app.config import settings

# Password Hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# JWT Tokens
def create_access_token(subject: Union[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": secrets.token_urlsafe(16),
        "sub": str(subject),
    }
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def verify_meta_webhook_signature(payload: bytes, signature: Optional[str]) -> bool:
    if not settings.META_APP_SECRET or not signature:
        return False
    expected = "sha256=" + hmac.new(
        settings.META_APP_SECRET.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)

# Token Encryption (Fernet / AES-128-CBC with HMAC-SHA256)
def get_fernet_cipher() -> Fernet:
    key = settings.ENCRYPTION_KEY.encode()
    return Fernet(key)

def encrypt_token(plain_token: str) -> str:
    if not plain_token:
        return ""
    cipher = get_fernet_cipher()
    return cipher.encrypt(plain_token.encode()).decode()

def decrypt_token(encrypted_token: str) -> str:
    if not encrypted_token:
        return ""
    cipher = get_fernet_cipher()
    return cipher.decrypt(encrypted_token.encode()).decode()
