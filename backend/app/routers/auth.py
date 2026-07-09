"""POST /api/auth/register, /login, /logout, GET /api/auth/me.

Real credentials from day one — no email-lookup simulation. `register` is the
dev/admin bootstrap path: it creates a brand-new org plus its first admin user
in one call (there is no invite flow yet; that's a later concern).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import CurrentUser, clear_session_cookie, get_current_user, hash_password, set_session_cookie, verify_password
from app.db.base import get_db_session
from app.db.scoped import find_user_by_email
from app.models import Organization, User, UserRole

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=255)
    org_name: str = Field(min_length=1, max_length=255)


class LoginRequest(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    role: str
    org_id: int


def _to_user_out(user: User) -> UserOut:
    return UserOut(id=user.id, email=user.email, role=user.role.value, org_id=user.org_id)


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, response: Response, session: Session = Depends(get_db_session)):
    if find_user_by_email(session, payload.email) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    org = Organization(name=payload.org_name)
    session.add(org)
    session.flush()

    user = User(org_id=org.id, email=payload.email, password_hash=hash_password(payload.password), role=UserRole.ADMIN)
    session.add(user)
    session.commit()
    session.refresh(user)

    set_session_cookie(response, user.id)
    return _to_user_out(user)


@router.post("/login", response_model=UserOut)
def login(payload: LoginRequest, response: Response, session: Session = Depends(get_db_session)):
    user = find_user_by_email(session, payload.email)
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    set_session_cookie(response, user.id)
    return _to_user_out(user)


@router.post("/logout")
def logout(response: Response):
    clear_session_cookie(response)
    return {"status": "ok"}


@router.get("/me", response_model=UserOut)
def me(current: CurrentUser = Depends(get_current_user)):
    return _to_user_out(current.user)
