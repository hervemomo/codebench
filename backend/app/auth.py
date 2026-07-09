"""Real authentication: password hashing, signed session cookies, and the
`get_current_user` dependency every business router depends on.

The session cookie carries only a user id (signed + HTTP-only, via
itsdangerous). org_id is never trusted from the client — it's read off the
User row on every request and is the only org_id the rest of the request
ever sees.
"""

from __future__ import annotations

from typing import Optional

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Cookie, Depends, HTTPException, Response, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.base import get_db_session
from app.db.scoped import get_user_by_id_unscoped
from app.models import User

SESSION_COOKIE_NAME = "cb_session"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 7  # 7 days

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().session_secret_key, salt="cb-session")


def create_session_token(user_id: int) -> str:
    return _serializer().dumps({"user_id": user_id})


def set_session_cookie(response: Response, user_id: int) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=create_session_token(user_id),
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=False,  # flip to True once served over TLS in a real deployment
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME)


def _read_session_token(token: Optional[str]) -> Optional[int]:
    if not token:
        return None
    try:
        data = _serializer().loads(token, max_age=SESSION_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None
    return data.get("user_id")


class CurrentUser:
    """Resolved from the session cookie. `org_id` is the only org_id the
    rest of the request is allowed to use."""

    def __init__(self, user: User):
        self.user = user
        self.org_id = user.org_id


def get_current_user(
    cb_session: Optional[str] = Cookie(default=None),
    session: Session = Depends(get_db_session),
) -> CurrentUser:
    user_id = _read_session_token(cb_session)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user = get_user_by_id_unscoped(session, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return CurrentUser(user)
