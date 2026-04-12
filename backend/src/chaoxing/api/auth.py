from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import get_current_active_user
from ..auth.schemas import (
    ChangePasswordRequest,
    RefreshTokenRequest,
    Token,
    UserCreate,
    UserLogin,
    UserPublic,
)
from ..auth.utils import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
    verify_token,
)
from ..db.database import get_db
from ..models.enums import UserRole
from ..models.invite import Invite
from ..models.user import User
from .rate_limit import login_limiter, register_limiter

router = APIRouter()


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserCreate, _rate=Depends(register_limiter), db: AsyncSession = Depends(get_db)
) -> User:
    if not payload.invite_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite code is required")
    if await User.get_by_email(db, payload.email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already exists")
    if await User.get_by_username(db, payload.username):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists")

    invite = await load_invite_by_code(db, payload.invite_code)
    if invite is None or not is_invite_usable(invite):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid invite code")

    invite.used_count += 1
    user = User(
        email=payload.email,
        username=payload.username,
        display_name=payload.display_name,
        password_hash=get_password_hash(payload.password),
        role=UserRole.USER,
        is_active=True,
        must_change_password=False,
        invited_by_user_id=invite.created_by_user_id,
        invite_code_id=invite.id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=Token)
async def login(
    payload: UserLogin, _rate=Depends(login_limiter), db: AsyncSession = Depends(get_db)
) -> Token:
    user = await User.get_by_username(db, payload.username)
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
    return issue_tokens_for_user(user)


@router.post("/refresh", response_model=Token)
async def refresh_token(
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> Token:
    token_payload = verify_token(payload.refresh_token)
    if token_payload is None or token_payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    try:
        user_id = int(token_payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user = await User.get(db, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    return issue_tokens_for_user(user)


@router.get("/me", response_model=UserPublic)
async def me(current_user: User = Depends(get_current_active_user)) -> User:
    return current_user


@router.post("/change-password", response_model=UserPublic)
async def change_password(
    payload: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> User:
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    current_user.password_hash = get_password_hash(payload.new_password)
    current_user.must_change_password = False
    await db.commit()
    await db.refresh(current_user)
    return current_user


async def load_invite_by_code(db: AsyncSession, invite_code: str) -> Invite | None:
    result = await db.execute(select(Invite).where(Invite.code == invite_code))
    return result.scalar_one_or_none()


def is_invite_usable(invite: Invite) -> bool:
    if not invite.is_active:
        return False
    if invite.expires_at is not None and invite.expires_at <= datetime.now(timezone.utc):
        return False
    return invite.used_count < invite.max_uses


def issue_tokens_for_user(user: User) -> Token:
    claims = {"sub": str(user.id), "role": user.role}
    return Token(
        access_token=create_access_token(claims),
        refresh_token=create_refresh_token(claims),
    )
