from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel, IDMixin, TimestampMixin
from .enums import ChaoxingAuthType


class ChaoxingAccount(BaseModel, IDMixin, TimestampMixin):
    __tablename__ = "chaoxing_accounts"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    auth_type: Mapped[ChaoxingAuthType] = mapped_column(
        Enum(ChaoxingAuthType), default=ChaoxingAuthType.PASSWORD, nullable=False
    )
    username_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    cookies_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_login_valid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="chaoxing_accounts")
    study_runs = relationship("StudyRun", back_populates="account")
