from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import get_current_active_user
from ..core.chaoxing.crypto import AESCipher
from ..core.services.auth_service import AuthService
from ..core.services.course_service import CourseService
from ..core.services.session_service import SessionService
from ..db.database import get_db
from ..models.chaoxing_account import ChaoxingAccount
from ..models.enums import ChaoxingAuthType
from ..models.user import User

router = APIRouter()


class ChaoxingAccountCreate(BaseModel):
    display_name: str | None = Field(default=None, max_length=100)
    auth_type: ChaoxingAuthType
    username: str | None = None
    password: str | None = None
    cookies: dict[str, str] | None = None


class ChaoxingAccountResponse(BaseModel):
    id: int
    display_name: str | None
    auth_type: ChaoxingAuthType
    is_login_valid: bool
    last_synced_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AccountActionResponse(BaseModel):
    account_id: int
    status: str
    message: str
    is_login_valid: bool


class AccountDeleteResponse(BaseModel):
    account_id: int
    status: str


class AccountSyncResponse(BaseModel):
    account_id: int
    status: str
    course_count: int
    courses: list[dict[str, Any]]
    last_synced_at: datetime


@router.post("", response_model=ChaoxingAccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    payload: ChaoxingAccountCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ChaoxingAccount:
    validate_account_payload(payload)
    cipher = AESCipher()
    account = ChaoxingAccount(
        user_id=current_user.id,
        display_name=payload.display_name,
        auth_type=payload.auth_type,
        username_encrypted=encrypt_optional(cipher, payload.username),
        password_encrypted=encrypt_optional(cipher, payload.password),
        cookies_encrypted=encrypt_optional(
            cipher,
            json.dumps(payload.cookies, ensure_ascii=False) if payload.cookies is not None else None,
        ),
        is_login_valid=False,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


@router.get("", response_model=list[ChaoxingAccountResponse])
async def list_accounts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[ChaoxingAccount]:
    return await load_user_accounts(db, current_user)


@router.delete("/{account_id}", response_model=AccountDeleteResponse)
async def delete_account(
    account_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> AccountDeleteResponse:
    account = await load_user_account(db, current_user, account_id)
    await db.delete(account)
    await db.commit()
    return AccountDeleteResponse(account_id=account.id, status="deleted")


@router.post("/{account_id}/verify", response_model=AccountActionResponse)
async def verify_account(
    account_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> AccountActionResponse:
    account = await load_user_account(db, current_user, account_id)
    result = await verify_account_session(account)
    account.is_login_valid = result["is_login_valid"]
    await db.commit()
    await db.refresh(account)
    return AccountActionResponse(account_id=account.id, **result)


@router.post("/{account_id}/sync-courses", response_model=AccountSyncResponse)
async def sync_courses(
    account_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> AccountSyncResponse:
    account = await load_user_account(db, current_user, account_id)
    courses = await sync_account_courses(account)
    account.is_login_valid = True
    account.last_synced_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(account)
    return AccountSyncResponse(
        account_id=account.id,
        status="success",
        course_count=len(courses),
        courses=courses,
        last_synced_at=account.last_synced_at,
    )


def validate_account_payload(payload: ChaoxingAccountCreate) -> None:
    if payload.auth_type == ChaoxingAuthType.PASSWORD:
        if not payload.username or not payload.password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username and password are required for password login",
            )
    elif payload.auth_type == ChaoxingAuthType.COOKIES and not payload.cookies:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cookies are required for cookie login",
        )


async def load_user_accounts(db: AsyncSession, current_user: User) -> list[ChaoxingAccount]:
    result = await db.execute(
        select(ChaoxingAccount).where(ChaoxingAccount.user_id == current_user.id)
    )
    return list(result.scalars().all())


async def load_user_account(
    db: AsyncSession,
    current_user: User,
    account_id: int,
) -> ChaoxingAccount:
    result = await db.execute(
        select(ChaoxingAccount).where(
            ChaoxingAccount.user_id == current_user.id,
            ChaoxingAccount.id == account_id,
        )
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return account


async def verify_account_session(account: ChaoxingAccount) -> dict[str, Any]:
    session_service = SessionService()
    auth_service = AuthService(session_service)
    account_payload, login_with_cookies = build_login_payload(account)
    result = await auth_service.login(str(account.id), account_payload, login_with_cookies)
    await session_service.close_all()
    return {
        "status": result["status"],
        "message": result["message"],
        "is_login_valid": result["status"] == "success",
    }


async def sync_account_courses(account: ChaoxingAccount) -> list[dict[str, Any]]:
    session_service = SessionService()
    auth_service = AuthService(session_service)
    course_service = CourseService(session_service)
    account_payload, login_with_cookies = build_login_payload(account)
    login_result = await auth_service.login(str(account.id), account_payload, login_with_cookies)
    if login_result["status"] != "success":
        await session_service.close_all()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=login_result["message"])

    courses = await course_service.get_course_list(str(account.id))
    await session_service.close_all()
    return courses


def build_login_payload(account: ChaoxingAccount) -> tuple[dict[str, str], bool]:
    cipher = AESCipher()
    if account.auth_type == ChaoxingAuthType.COOKIES:
        if not account.cookies_encrypted:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing cookies")
        return {"cookies": cipher.decrypt(account.cookies_encrypted)}, True

    if not account.username_encrypted or not account.password_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing username/password credentials",
        )
    return {
        "username": cipher.decrypt(account.username_encrypted),
        "password": cipher.decrypt(account.password_encrypted),
    }, False


def encrypt_optional(cipher: AESCipher, value: str | None) -> str | None:
    if value is None:
        return None
    return cipher.encrypt(value)
