"""TikuService — orchestrator for quiz answer lookup with caching and fallback chain."""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Optional

from .base import (
    BaseTikuProvider,
    TikuQueryInfo,
    TikuResult,
    check_answer,
    check_judgement,
)
from .adapter import TikuAdapter
from .like import TikuLike
from .openai_compat import OpenAICompatProvider
from .siliconflow import SiliconFlowProvider
from .yanxi import TikuYanxi

logger = logging.getLogger(__name__)

_PROVIDER_CLASSES: dict[str, type[BaseTikuProvider]] = {
    "yanxi": TikuYanxi,
    "like": TikuLike,
    "adapter": TikuAdapter,
    "openai_compat": OpenAICompatProvider,
    "siliconflow": SiliconFlowProvider,
}

# Default keyword lists for 判断题 (true/false) detection
DEFAULT_TRUE_KEYWORDS = [
    "正确", "对", "是", "√", "T", "true", "True", "TRUE",
    "right", "yes", "Yes", "对的",
]
DEFAULT_FALSE_KEYWORDS = [
    "错误", "错", "否", "×", "F", "false", "False", "FALSE",
    "wrong", "no", "No", "错的",
]


class TikuService:
    """Manages a chain of tiku providers with caching and answer validation.

    This is a runtime service (not a database-backed service) — it can be
    initialised from ``TikuProvider`` DB rows or from raw config dicts.
    """

    def __init__(
        self,
        *,
        db_session=None,
        cover_rate: float = 0.8,
        auto_submit: bool = False,
        true_keywords: list[str] | None = None,
        false_keywords: list[str] | None = None,
    ) -> None:
        self._providers: list[BaseTikuProvider] = []
        self._db_session = db_session
        self.cover_rate = cover_rate
        self.auto_submit = auto_submit
        self.true_keywords = true_keywords or list(DEFAULT_TRUE_KEYWORDS)
        self.false_keywords = false_keywords or list(DEFAULT_FALSE_KEYWORDS)
        # In-memory cache (question_hash → answer)
        self._cache: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Provider management
    # ------------------------------------------------------------------

    async def add_provider(self, provider_type: str, config: dict[str, Any]) -> None:
        """Instantiate and initialise a provider, then add it to the chain."""
        cls = _PROVIDER_CLASSES.get(provider_type)
        if cls is None:
            logger.warning("Unknown tiku provider type: %s", provider_type)
            return
        provider = cls()
        await provider.init(config)
        self._providers.append(provider)
        logger.info("Added tiku provider: %s (%s)", provider.name, provider_type)

    async def load_providers_from_db(self, user_id: int) -> None:
        """Load active providers for a user from the DB (TikuProvider model)."""
        if self._db_session is None:
            return
        from ...models.tiku_provider import TikuProvider

        from sqlalchemy import select

        stmt = (
            select(TikuProvider)
            .where(TikuProvider.user_id == user_id, TikuProvider.is_active.is_(True))
            .order_by(TikuProvider.priority)
        )
        result = await self._db_session.execute(stmt)
        rows = result.scalars().all()
        for row in rows:
            await self.add_provider(row.provider_type.value, row.config_encrypted)

    # ------------------------------------------------------------------
    # Query interface
    # ------------------------------------------------------------------

    async def query(self, question: dict[str, Any]) -> Optional[TikuResult]:
        """Query all providers in order for a single question.

        Returns the first valid result, or None.
        """
        q_info = TikuQueryInfo.from_question(question)
        if not q_info.title:
            return None

        # Check in-memory cache
        cache_key = self._hash_question(q_info.title)
        if cache_key in self._cache:
            logger.debug("Cache hit for: %s", q_info.title[:50])
            return TikuResult(
                answer=self._cache[cache_key],
                provider_name="cache",
                from_cache=True,
            )

        # Check DB cache
        cached = await self._get_db_cache(cache_key)
        if cached is not None:
            self._cache[cache_key] = cached
            return TikuResult(answer=cached, provider_name="db_cache", from_cache=True)

        # Try each provider in order
        for provider in self._providers:
            try:
                raw_answer = await provider.query(q_info)
            except Exception:
                logger.exception("Provider %s raised during query", provider.name)
                continue

            if not raw_answer:
                continue

            raw_answer = raw_answer.strip()
            if not raw_answer:
                continue

            # Validate answer type matches question type
            if not check_answer(
                raw_answer,
                q_info.question_type,
                self.true_keywords,
                self.false_keywords,
            ):
                logger.info(
                    "Provider %s answer type mismatch for '%s', skipping",
                    provider.name,
                    q_info.title[:40],
                )
                continue

            # Valid answer — cache and return
            self._cache[cache_key] = raw_answer
            await self._set_db_cache(cache_key, q_info.title, raw_answer)

            return TikuResult(
                answer=raw_answer,
                provider_name=provider.name,
                from_cache=False,
            )

        logger.warning("No provider found answer for: %s", q_info.title[:60])
        return None

    # ------------------------------------------------------------------
    # Judgment helpers
    # ------------------------------------------------------------------

    def judgement_select(self, answer: str) -> bool:
        """Convert a provider's judgment answer to boolean (True=正确, False=错误)."""
        answer = answer.strip()
        result = check_judgement(answer, self.true_keywords, self.false_keywords)
        if result == 1:
            return True
        if result == 0:
            return False
        # Unknown — random fallback logged in caller
        import random
        return random.choice([True, False])

    def get_submit_flag(self) -> str:
        """Return pyFlag value: '' for submit, '1' for save-only."""
        return "" if self.auto_submit else "1"

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _hash_question(title: str) -> str:
        return hashlib.sha256(title.encode("utf-8")).hexdigest()

    async def _get_db_cache(self, question_hash: str) -> str | None:
        if self._db_session is None:
            return None
        try:
            from ...models.tiku_cache_entry import TikuCacheEntry
            from sqlalchemy import select

            stmt = select(TikuCacheEntry).where(
                TikuCacheEntry.question_hash == question_hash
            )
            result = await self._db_session.execute(stmt)
            row = result.scalar_one_or_none()
            return row.answer_text if row else None
        except Exception:
            logger.debug("DB cache lookup failed", exc_info=True)
            return None

    async def _set_db_cache(self, question_hash: str, title: str, answer: str) -> None:
        if self._db_session is None:
            return
        try:
            from ...models.tiku_cache_entry import TikuCacheEntry

            entry = TikuCacheEntry(
                question_hash=question_hash,
                question_text=title,
                answer_text=answer,
            )
            self._db_session.add(entry)
            await self._db_session.flush()
        except Exception:
            logger.debug("DB cache write failed", exc_info=True)
