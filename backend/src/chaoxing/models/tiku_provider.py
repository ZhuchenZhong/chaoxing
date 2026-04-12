import enum

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel, IDMixin, TimestampMixin


class TikuProviderType(str, enum.Enum):
    YANXI = "yanxi"
    LIKE = "like"
    ADAPTER = "adapter"
    OPENAI_COMPAT = "openai_compat"
    SILICONFLOW = "siliconflow"


class TikuProvider(BaseModel, IDMixin, TimestampMixin):
    __tablename__ = "tiku_providers"

    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_type: Mapped[TikuProviderType] = mapped_column(Enum(TikuProviderType), nullable=False)
    config_encrypted: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user = relationship("User", back_populates="tiku_providers")
