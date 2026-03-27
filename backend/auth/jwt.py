from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jose import jwt

from backend.config.settings import settings


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(*, subject: str, username: str, is_admin: bool) -> str:
    expire = _utcnow() + timedelta(minutes=settings.auth_token_expire_minutes)
    payload: Dict[str, Any] = {
        "sub": subject,
        "username": username,
        "role": "admin" if is_admin else "user",
        "iat": int(_utcnow().timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.auth_secret_key, algorithm=settings.auth_algorithm)


def decode_access_token(token: str) -> Dict[str, Any]:
    return jwt.decode(
        token,
        settings.auth_secret_key,
        algorithms=[settings.auth_algorithm],
        options={"verify_aud": False},
    )

