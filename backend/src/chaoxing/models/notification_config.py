import enum

from sqlalchemy import Boolean, Enum, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel, IDMixin, TimestampMixin


class NotificationProviderType(str, enum.Enum):
    SERVERCHAN = "serverchan"
    QMSG = "qmsg"
    BARK = "bark"
    TELEGRAM = "telegram"


class NotificationConfig(BaseModel, IDMixin, TimestampMixin):
    __tablename__ = "notification_configs"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    provider: Mapped[NotificationProviderType] = mapped_column(
        Enum(NotificationProviderType), nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    settings_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    user = relationship("User", back_populates="notification_configs")
