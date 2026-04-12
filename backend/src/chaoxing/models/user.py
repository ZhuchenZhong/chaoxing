from sqlalchemy import select
from sqlalchemy import Boolean, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel, IDMixin, TimestampMixin
from .enums import UserRole


class User(BaseModel, IDMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.USER, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    invited_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    invite_code_id: Mapped[int | None] = mapped_column(ForeignKey("invites.id"), nullable=True)

    invited_by = relationship(
        "User",
        remote_side="User.id",
        back_populates="invited_users",
        foreign_keys=[invited_by_user_id],
    )
    invited_users = relationship(
        "User", back_populates="invited_by", foreign_keys=[invited_by_user_id]
    )
    invite_code = relationship(
        "Invite", back_populates="invited_users", foreign_keys=[invite_code_id]
    )
    created_invites = relationship(
        "Invite", back_populates="created_by", foreign_keys="Invite.created_by_user_id"
    )
    wallet = relationship(
        "Wallet", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    chaoxing_accounts = relationship(
        "ChaoxingAccount", back_populates="user", cascade="all, delete-orphan"
    )
    study_profiles = relationship(
        "StudyProfile", back_populates="user", cascade="all, delete-orphan"
    )
    study_runs = relationship("StudyRun", back_populates="user")
    wallet_transactions = relationship("WalletTransaction", back_populates="user")
    recharge_orders = relationship(
        "RechargeOrder", back_populates="user", foreign_keys="RechargeOrder.user_id"
    )
    reviewed_recharge_orders = relationship(
        "RechargeOrder",
        back_populates="reviewer",
        foreign_keys="RechargeOrder.reviewed_by_user_id",
    )
    tiku_providers = relationship("TikuProvider", back_populates="user")
    notification_configs = relationship(
        "NotificationConfig", back_populates="user", cascade="all, delete-orphan"
    )

    @classmethod
    async def get(cls, db, user_id: int):
        result = await db.execute(select(cls).where(cls.id == user_id))
        return result.scalar_one_or_none()

    @classmethod
    async def get_by_email(cls, db, email: str):
        result = await db.execute(select(cls).where(cls.email == email))
        return result.scalar_one_or_none()

    @classmethod
    async def get_by_username(cls, db, username: str):
        result = await db.execute(select(cls).where(cls.username == username))
        return result.scalar_one_or_none()
