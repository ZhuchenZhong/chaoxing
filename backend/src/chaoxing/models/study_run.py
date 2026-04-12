from datetime import datetime
import enum

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel, IDMixin, TimestampMixin


class StudyRunStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    STOPPING = "stopping"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StudyRunEventLevel(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class StudyRun(BaseModel, IDMixin, TimestampMixin):
    __tablename__ = "study_runs"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("chaoxing_accounts.id"), nullable=False, index=True
    )
    profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("study_profiles.id"), nullable=True, index=True
    )
    course_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[StudyRunStatus] = mapped_column(
        Enum(StudyRunStatus), default=StudyRunStatus.QUEUED, nullable=False, index=True
    )
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    progress_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="study_runs")
    account = relationship("ChaoxingAccount", back_populates="study_runs")
    profile = relationship("StudyProfile", back_populates="study_runs")
    events = relationship("StudyRunEvent", back_populates="run", cascade="all, delete-orphan")
    wallet_transactions = relationship("WalletTransaction", back_populates="related_run")


class StudyRunEvent(BaseModel, IDMixin):
    __tablename__ = "study_run_events"

    run_id: Mapped[int] = mapped_column(ForeignKey("study_runs.id"), nullable=False, index=True)
    level: Mapped[StudyRunEventLevel] = mapped_column(Enum(StudyRunEventLevel), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    detail_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    run = relationship("StudyRun", back_populates="events")
