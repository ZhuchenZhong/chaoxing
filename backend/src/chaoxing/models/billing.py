from datetime import datetime
import enum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel, IDMixin, TimestampMixin


class RechargeOrderStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class CreditPackage(BaseModel, IDMixin):
    __tablename__ = "credit_packages"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    credits: Mapped[int] = mapped_column(Integer, nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    recharge_orders = relationship("RechargeOrder", back_populates="package")


class RechargeOrder(BaseModel, IDMixin, TimestampMixin):
    __tablename__ = "recharge_orders"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    package_id: Mapped[int | None] = mapped_column(
        ForeignKey("credit_packages.id"), nullable=True, index=True
    )
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    requested_credits: Mapped[int] = mapped_column(Integer, nullable=False)
    payment_channel: Mapped[str | None] = mapped_column(String(50), nullable=True)
    payment_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    proof_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[RechargeOrderStatus] = mapped_column(
        Enum(RechargeOrderStatus), default=RechargeOrderStatus.PENDING, nullable=False, index=True
    )
    reviewed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    user = relationship("User", back_populates="recharge_orders", foreign_keys=[user_id])
    reviewer = relationship(
        "User", back_populates="reviewed_recharge_orders", foreign_keys=[reviewed_by_user_id]
    )
    package = relationship("CreditPackage", back_populates="recharge_orders")
