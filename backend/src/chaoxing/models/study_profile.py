from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, JSON, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel, IDMixin, TimestampMixin
from .enums import NotOpenAction


class StudyProfile(BaseModel, IDMixin, TimestampMixin):
    __tablename__ = "study_profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    speed: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=Decimal("1.00"), nullable=False)
    notopen_action: Mapped[NotOpenAction] = mapped_column(
        Enum(NotOpenAction), default=NotOpenAction.RETRY, nullable=False
    )
    tiku_config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    submit_config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    user = relationship("User", back_populates="study_profiles")
    study_runs = relationship("StudyRun", back_populates="profile")
