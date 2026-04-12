from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import get_current_admin_user
from ..auth.schemas import UserPublic
from ..db.database import get_db
from ..models.billing import RechargeOrder, RechargeOrderStatus
from ..models.enums import UserRole
from ..models.invite import Invite
from ..models.study_run import StudyRun, StudyRunStatus
from ..models.system_setting import SystemSetting
from ..models.tiku_provider import TikuProvider, TikuProviderType
from ..models.user import User
from ..models.wallet import WalletTransaction
from .wallet import RechargeOrderResponse, get_or_create_user_wallet

router = APIRouter()


class AdminUserUpdate(BaseModel):
    display_name: str | None = None
    role: str | None = None
    is_active: bool | None = None
    must_change_password: bool | None = None


class AdminTaskResponse(BaseModel):
    id: int
    user_id: int
    account_id: int
    profile_id: int | None
    course_ids: list[str]
    status: StudyRunStatus
    celery_task_id: str | None
    progress_json: dict[str, Any]
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InviteCreate(BaseModel):
    code: str
    max_uses: int = 1
    bonus_credits: int = 0
    expires_at: datetime | None = None


class InviteResponse(BaseModel):
    id: int
    code: str
    created_by_user_id: int | None
    max_uses: int
    used_count: int
    bonus_credits: int
    is_active: bool
    expires_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TikuProviderCreate(BaseModel):
    name: str
    provider_type: TikuProviderType
    config: dict[str, Any]
    priority: int = 100
    is_active: bool = True
    user_id: int | None = None


class TikuProviderResponse(BaseModel):
    id: int
    user_id: int | None
    name: str
    provider_type: TikuProviderType
    config_encrypted: dict[str, Any]
    priority: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RechargeOrderReview(BaseModel):
    status: RechargeOrderStatus
    review_note: str | None = None


class SystemSettingUpdate(BaseModel):
    value: dict[str, Any]


class SystemSettingResponse(BaseModel):
    key: str
    value: dict[str, Any]
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


@router.get("/users", response_model=list[UserPublic])
async def get_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> list[User]:
    return await load_users(db, current_user)


@router.put("/users/{user_id}", response_model=UserPublic)
async def update_user(
    user_id: int,
    payload: AdminUserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> User:
    user = await load_user_by_id(db, current_user, user_id)
    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.role is not None:
        user.role = UserRole(payload.role)
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.must_change_password is not None:
        user.must_change_password = payload.must_change_password
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/tasks", response_model=list[AdminTaskResponse])
async def get_tasks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> list[StudyRun]:
    return await load_study_runs(db, current_user)


@router.get("/recharge-orders", response_model=list[RechargeOrderResponse])
async def get_recharge_orders(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> list[RechargeOrder]:
    return await load_recharge_orders(db, current_user)


@router.put("/recharge-orders/{order_id}", response_model=RechargeOrderResponse)
async def review_recharge_order(
    order_id: int,
    payload: RechargeOrderReview,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> RechargeOrder:
    order = await load_recharge_order(db, current_user, order_id)
    should_credit = (
        payload.status == RechargeOrderStatus.APPROVED
        and order.status != RechargeOrderStatus.APPROVED
    )
    order.status = payload.status
    order.review_note = payload.review_note
    order.reviewed_by_user_id = current_user.id
    order.reviewed_at = datetime.now(timezone.utc)

    if should_credit:
        wallet_owner = SimpleNamespace(id=order.user_id)
        wallet = await get_or_create_user_wallet(db, wallet_owner)
        wallet.balance += order.requested_credits
        db.add(
            WalletTransaction(
                wallet_id=wallet.id,
                user_id=order.user_id,
                delta=order.requested_credits,
                balance_after=wallet.balance,
                reason="recharge_order_approved",
                metadata_json={"recharge_order_id": order.id},
                created_at=datetime.now(timezone.utc),
            )
        )

    await db.commit()
    await db.refresh(order)
    return order


@router.get("/invites", response_model=list[InviteResponse])
async def get_invites(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> list[Invite]:
    return await load_invites(db, current_user)


@router.post("/invites", response_model=InviteResponse, status_code=status.HTTP_201_CREATED)
async def create_invite(
    payload: InviteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> Invite:
    invite = Invite(
        code=payload.code,
        created_by_user_id=current_user.id,
        max_uses=payload.max_uses,
        used_count=0,
        bonus_credits=payload.bonus_credits,
        is_active=True,
        expires_at=payload.expires_at,
        created_at=datetime.now(timezone.utc),
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    return invite


@router.delete("/invites/{invite_id}", response_model=InviteResponse)
async def delete_invite(
    invite_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> Invite:
    invite = await load_invite(db, current_user, invite_id)
    invite.is_active = False
    await db.commit()
    return invite


@router.get("/tiku-providers", response_model=list[TikuProviderResponse])
async def get_tiku_providers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> list[TikuProvider]:
    return await load_tiku_providers(db, current_user)


@router.post(
    "/tiku-providers",
    response_model=TikuProviderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_tiku_provider(
    payload: TikuProviderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> TikuProvider:
    provider = TikuProvider(
        user_id=payload.user_id,
        name=payload.name,
        provider_type=payload.provider_type,
        config_encrypted=payload.config,
        priority=payload.priority,
        is_active=payload.is_active,
    )
    db.add(provider)
    await db.commit()
    await db.refresh(provider)
    return provider


@router.get("/settings", response_model=list[SystemSettingResponse])
async def get_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> list[SystemSetting]:
    return await load_system_settings(db, current_user)


@router.put("/settings/{key}", response_model=SystemSettingResponse)
async def update_setting(
    key: str,
    payload: SystemSettingUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> SystemSetting:
    setting = await load_system_setting(db, current_user, key)
    if setting is None:
        setting = SystemSetting(
            key=key,
            value=payload.value,
            updated_at=datetime.now(timezone.utc),
        )
        db.add(setting)
    else:
        setting.value = payload.value
        setting.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(setting)
    return setting


async def load_users(db: AsyncSession, _current_user: User) -> list[User]:
    result = await db.execute(select(User).order_by(User.id.asc()))
    return list(result.scalars().all())


async def load_user_by_id(db: AsyncSession, _current_user: User, user_id: int) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


async def load_study_runs(db: AsyncSession, _current_user: User) -> list[StudyRun]:
    result = await db.execute(select(StudyRun).order_by(StudyRun.created_at.desc(), StudyRun.id.desc()))
    return list(result.scalars().all())


async def load_recharge_orders(db: AsyncSession, _current_user: User) -> list[RechargeOrder]:
    result = await db.execute(
        select(RechargeOrder).order_by(RechargeOrder.created_at.desc(), RechargeOrder.id.desc())
    )
    return list(result.scalars().all())


async def load_recharge_order(
    db: AsyncSession,
    _current_user: User,
    order_id: int,
) -> RechargeOrder:
    result = await db.execute(select(RechargeOrder).where(RechargeOrder.id == order_id))
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recharge order not found",
        )
    return order


async def load_invites(db: AsyncSession, _current_user: User) -> list[Invite]:
    result = await db.execute(select(Invite).order_by(Invite.created_at.desc(), Invite.id.desc()))
    return list(result.scalars().all())


async def load_invite(db: AsyncSession, _current_user: User, invite_id: int) -> Invite:
    result = await db.execute(select(Invite).where(Invite.id == invite_id))
    invite = result.scalar_one_or_none()
    if invite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")
    return invite


async def load_tiku_providers(db: AsyncSession, _current_user: User) -> list[TikuProvider]:
    result = await db.execute(
        select(TikuProvider).order_by(TikuProvider.priority.asc(), TikuProvider.id.asc())
    )
    return list(result.scalars().all())


async def load_system_settings(db: AsyncSession, _current_user: User) -> list[SystemSetting]:
    result = await db.execute(select(SystemSetting).order_by(SystemSetting.key.asc()))
    return list(result.scalars().all())


async def load_system_setting(
    db: AsyncSession,
    _current_user: User,
    key: str,
) -> SystemSetting | None:
    result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
    return result.scalar_one_or_none()
