from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel, IDMixin


class Invite(BaseModel, IDMixin):
    __tablename__ = "invites"

    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    max_uses: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    used_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    bonus_credits: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    created_by = relationship(
        "User", back_populates="created_invites", foreign_keys=[created_by_user_id]
    )
    invited_users = relationship(
        "User", back_populates="invite_code", foreign_keys="User.invite_code_id"
    )
