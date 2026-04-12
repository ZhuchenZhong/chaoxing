from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from passlib.context import CryptContext

from ..config import settings


def _build_password_context() -> CryptContext:
    bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    try:
        probe_hash = bcrypt_context.hash("codex-password-probe")
        if bcrypt_context.verify("codex-password-probe", probe_hash):
            return bcrypt_context
    except Exception:
        return CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

    return CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


pwd_context = _build_password_context()


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    to_encode["exp"] = expire
    to_encode["type"] = "access"
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(data: dict[str, Any]) -> str:
    to_encode = data.copy()
    to_encode["exp"] = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_token_expire_days)
    to_encode["type"] = "refresh"
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None
