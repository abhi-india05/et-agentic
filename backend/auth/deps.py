from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from backend.auth.jwt import decode_access_token
from backend.config.settings import settings
from backend.deps import get_user_repo
from backend.repositories.users import UserRepository

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthUser:
    user_id: str
    username: str
    is_admin: bool = False


def _extract_token(
    request: Request, credentials: Optional[HTTPAuthorizationCredentials]
) -> Optional[str]:
    if credentials and (credentials.scheme or "").lower() == "bearer":
        return credentials.credentials
    cookie_name = settings.auth_cookie_name
    return request.cookies.get(cookie_name)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    user_repo: UserRepository = Depends(get_user_repo),
) -> AuthUser:
    if not settings.auth_enabled:
        user = AuthUser(user_id="anonymous", username="anonymous", is_admin=False)
        request.state.user = user
        return user

    token = _extract_token(request, credentials)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authentication token",
        )

    try:
        payload = decode_access_token(token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Token verification failed")

    sub = payload.get("sub")
    username = payload.get("username") or ""
    role = payload.get("role") or ""
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    if str(role).lower() == "admin" or str(sub) == settings.auth_username:
        user = AuthUser(user_id=str(sub), username=username or settings.auth_username, is_admin=True)
        request.state.user = user
        return user

    db_user = await user_repo.get_by_id(str(sub))
    if not db_user and username:
        # Back-compat: older tokens used username in `sub`.
        db_user = await user_repo.get_by_username(str(sub)) or await user_repo.get_by_username(username)
    if not db_user:
        raise HTTPException(status_code=401, detail="User not found")

    user = AuthUser(user_id=db_user.user_id, username=db_user.username, is_admin=False)
    request.state.user = user
    return user

