from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import get_current_active_user
from ..db.database import get_db
from ..models.billing import RechargeOrder, RechargeOrderStatus
from ..models.user import User
from ..models.wallet import Wallet, WalletTransaction

router = APIRouter()


class WalletResponse(BaseModel):
    id: int
    user_id: int
    balance: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WalletTransactionResponse(BaseModel):
    id: int
    wallet_id: int
    user_id: int
    delta: int
    balance_after: int
    reason: str
    related_run_id: int | None
    metadata_json: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RechargeOrderCreate(BaseModel):
    amount_cents: int
    requested_credits: int
    payment_channel: str | None = None
    payment_reference: str | None = None
    proof_path: str | None = None


class RechargeOrderResponse(BaseModel):
    id: int
    user_id: int
    package_id: int | None
    amount_cents: int
    requested_credits: int
    payment_channel: str | None
    payment_reference: str | None
    proof_path: str | None
    status: RechargeOrderStatus
    reviewed_by_user_id: int | None
    reviewed_at: datetime | None
    review_note: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=WalletResponse)
async def get_wallet(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Wallet:
    return await get_or_create_user_wallet(db, current_user)


@router.get("/transactions", response_model=list[WalletTransactionResponse])
async def get_wallet_transactions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[WalletTransaction]:
    return await load_wallet_transactions(db, current_user)


@router.post("/recharge", response_model=RechargeOrderResponse, status_code=201)
async def create_recharge_order(
    payload: RechargeOrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> RechargeOrder:
    order = RechargeOrder(
        user_id=current_user.id,
        amount_cents=payload.amount_cents,
        requested_credits=payload.requested_credits,
        payment_channel=payload.payment_channel,
        payment_reference=payload.payment_reference,
        proof_path=payload.proof_path,
        status=RechargeOrderStatus.PENDING,
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return order


async def get_or_create_user_wallet(db: AsyncSession, current_user: User) -> Wallet:
    result = await db.execute(select(Wallet).where(Wallet.user_id == current_user.id))
    wallet = result.scalar_one_or_none()
    if wallet is not None:
        return wallet

    wallet = Wallet(user_id=current_user.id, balance=0)
    db.add(wallet)
    await db.commit()
    await db.refresh(wallet)
    return wallet


async def load_wallet_transactions(db: AsyncSession, current_user: User) -> list[WalletTransaction]:
    result = await db.execute(
        select(WalletTransaction)
        .where(WalletTransaction.user_id == current_user.id)
        .order_by(WalletTransaction.created_at.desc(), WalletTransaction.id.desc())
    )
    return list(result.scalars().all())
