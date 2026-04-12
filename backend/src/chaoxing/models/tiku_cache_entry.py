from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel, IDMixin, TimestampMixin


class TikuCacheEntry(BaseModel, IDMixin, TimestampMixin):
    __tablename__ = "tiku_cache_entries"

    question_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
