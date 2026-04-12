"""Base class and data types for tiku providers."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class TikuQueryInfo:
    """Normalised question payload sent to tiku providers."""

    title: str
    question_type: str  # "single", "multiple", "completion", "judgement", "shortanswer"
    options: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    # Chaoxing numeric type codes
    TYPE_MAP: dict[str, str] = field(
        default_factory=lambda: {
            "0": "single",
            "1": "multiple",
            "2": "completion",
            "3": "judgement",
            "4": "shortanswer",
        },
        repr=False,
    )

    @classmethod
    def from_question(cls, question: dict[str, Any]) -> TikuQueryInfo:
        raw_type = str(question.get("type", "0"))
        type_map = {
            "0": "single",
            "1": "multiple",
            "2": "completion",
            "3": "judgement",
            "4": "shortanswer",
            "single": "single",
            "multiple": "multiple",
            "completion": "completion",
            "judgement": "judgement",
            "shortanswer": "shortanswer",
        }
        question_type = type_map.get(raw_type, "shortanswer")

        title = question.get("title", "")
        # Clean numbering and point values from title
        title = re.sub(r"^\d+", "", title)
        title = re.sub(r"（\d+(\.\d+)?分）$", "", title)
        # Strip HTML tags
        title = re.sub(r"<[^>]+>", "", title)
        title = re.sub(r"\s+", " ", title).strip()

        options = question.get("options", [])
        if isinstance(options, str):
            options = [o.strip() for o in options.split("\n") if o.strip()]

        return cls(
            title=title,
            question_type=question_type,
            options=options,
            raw=question,
        )


@dataclass
class TikuResult:
    """Result returned by a tiku provider."""

    answer: str
    provider_name: str
    from_cache: bool = False


# ---------------------------------------------------------------------------
# Answer splitting utility (ported from legacy answer_check.py)
# ---------------------------------------------------------------------------

CUT_CHARS = [
    "\n", ",", "，", "|", "\r", "\t", "#", "*", "-", "_",
    "+", "@", "~", "/", "\\", ".", "&", " ", "、",
]


def split_answer(answer: str | None) -> list[str] | None:
    """Split an answer string using the legacy delimiter list.

    Tries each delimiter in priority order; returns the first successful
    split or a single-element list as fallback.
    """
    if answer is None:
        return None
    answer = str(answer)
    for char in CUT_CHARS:
        if char not in answer:
            continue
        parts = [p.strip() for p in answer.split(char) if p.strip()]
        if parts:
            return parts
    stripped = answer.strip()
    return [stripped] if stripped else None


# ---------------------------------------------------------------------------
# Answer validation (ported from legacy answer_check.py)
# ---------------------------------------------------------------------------

def check_judgement(answer: str, true_list: list[str], false_list: list[str]) -> int:
    """Return 1 if answer matches a 'true' keyword, 0 for 'false', -1 otherwise."""
    if answer in true_list:
        return 1
    if answer in false_list:
        return 0
    return -1


def check_answer(
    answer: str,
    question_type: str,
    true_list: list[str],
    false_list: list[str],
) -> bool:
    """Validate that *answer* is plausible for the given *question_type*."""
    if question_type == "single":
        parts = split_answer(answer)
        return (
            parts is not None
            and len(parts) == 1
            and check_judgement(answer, true_list, false_list) == -1
        )
    if question_type == "multiple":
        parts = split_answer(answer)
        return (
            parts is not None
            and len(parts) > 0
            and check_judgement(answer, true_list, false_list) == -1
        )
    if question_type == "completion":
        return len(answer) > 0
    if question_type == "judgement":
        return check_judgement(answer, true_list, false_list) != -1
    # Unknown types: accept any non-empty answer
    return True


class BaseTikuProvider:
    """Abstract async tiku provider.

    Subclasses must implement ``_query`` and set ``name``.
    """

    name: str = "base"

    async def init(self, config: dict[str, Any]) -> None:
        """Initialise provider from a config dict (from TikuProvider.config_encrypted)."""

    async def query(self, q_info: TikuQueryInfo) -> Optional[str]:
        """Query the provider and return the raw answer string, or None."""
        try:
            return await self._query(q_info)
        except Exception:
            logger.exception("Tiku provider %s query failed", self.name)
            return None

    async def _query(self, q_info: TikuQueryInfo) -> Optional[str]:
        raise NotImplementedError

    async def check_connection(self) -> bool:
        """Verify the provider is reachable. Default: True."""
        return True
