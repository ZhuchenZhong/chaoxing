"""TikuLike (LIKE知识库) provider — https://www.datam.site/."""

from __future__ import annotations

import logging
import random
from typing import Any, Optional

import httpx

from .base import BaseTikuProvider, TikuQueryInfo

logger = logging.getLogger(__name__)

QUERY_API = "https://app.datam.site/api/v1/query"
BALANCE_API = "https://app.datam.site/api/v1/balance"


class TikuLike(BaseTikuProvider):
    name = "LIKE知识库"

    def __init__(self) -> None:
        self._tokens: list[str] = []
        self._balance: dict[str, int] = {}
        self._model: str | None = None
        self._search: bool = False
        self._vision: bool = True
        self._retry: bool = True
        self._retry_times: int = 3
        self._timeout: int = 300
        self._query_count: int = 0

    async def init(self, config: dict[str, Any]) -> None:
        tokens_raw = config.get("tokens", "")
        self._tokens = [t.strip() for t in tokens_raw.split(",") if t.strip()]
        self._model = config.get("likeapi_model") or None
        self._search = _to_bool(config.get("likeapi_search", False))
        self._vision = _to_bool(config.get("likeapi_vision", True))
        self._retry = _to_bool(config.get("likeapi_retry", True))
        self._retry_times = int(config.get("likeapi_retry_times", 3))
        if self._tokens:
            await self._update_balances()

    # ------------------------------------------------------------------
    # Public query
    # ------------------------------------------------------------------

    async def _query(self, q_info: TikuQueryInfo) -> Optional[str]:
        if not self._tokens:
            logger.error("%s: no tokens configured", self.name)
            return None

        token = self._pick_token()
        if not token:
            logger.error("%s: all tokens exhausted", self.name)
            return None

        question = self._build_question(q_info)

        result: str | None = None
        attempts = 0
        while result is None and attempts < self._retry_times:
            result = await self._query_single(token, question)
            attempts += 1
            if result is not None:
                self._balance[token] = max(self._balance.get(token, 0) - 1, 0)
                break
            if attempts < self._retry_times:
                logger.warning("%s: retry %d/%d", self.name, attempts + 1, self._retry_times)

        self._query_count = (self._query_count + 1) % 10
        if self._query_count == 0:
            await self._update_balances()

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _pick_token(self) -> str | None:
        available = [t for t in self._tokens if self._balance.get(t, 0) > 0]
        if available:
            return random.choice(available)
        # Fallback: try any token
        return random.choice(self._tokens) if self._tokens else None

    @staticmethod
    def _build_question(q_info: TikuQueryInfo) -> str:
        prefix_map = {
            "single": "【单选题】",
            "multiple": "【多选题】",
            "completion": "【填空题】",
            "judgement": "【判断题】",
        }
        prefix = prefix_map.get(q_info.question_type, "【其他类型题目】")
        question = f"{prefix}{q_info.title}\n"
        if q_info.question_type in ("single", "multiple") and q_info.options:
            question += f"选项为: {', '.join(q_info.options)}\n"
        return question

    async def _query_single(self, token: str, question: str) -> str | None:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }
        payload = {
            "query": question,
            "model": self._model or "",
            "search": self._search,
            "vision": self._vision,
        }
        try:
            async with httpx.AsyncClient(verify=False, timeout=self._timeout) as client:
                resp = await client.post(QUERY_API, json=payload, headers=headers)
        except httpx.TimeoutException:
            logger.error("%s: query timed out", self.name)
            return None
        except httpx.ConnectError:
            logger.error("%s: connection error", self.name)
            return None
        except Exception:
            logger.exception("%s: unexpected error", self.name)
            return None

        if resp.status_code != 200:
            logger.error("%s: HTTP %d", self.name, resp.status_code)
            return None

        return self._parse_response(resp)

    def _parse_response(self, resp: httpx.Response) -> str | None:
        try:
            data = resp.json()
        except Exception:
            logger.error("%s: invalid JSON response", self.name)
            return None

        results = data.get("results", {})
        if not isinstance(results, dict):
            return None
        output = results.get("output")
        if not isinstance(output, dict):
            return None

        q_type = output.get("questionType")
        answer = output.get("answer")
        if not isinstance(answer, dict):
            return None

        return self._extract_answer_by_type(q_type, answer)

    @staticmethod
    def _extract_answer_by_type(q_type: str | None, answer: dict) -> str | None:
        if q_type == "CHOICE":
            opts = answer.get("selectedOptions", [])
            if isinstance(opts, list):
                valid = [str(o) for o in opts if o is not None and str(o).strip()]
                return "\n".join(valid) if valid else None
        elif q_type == "FILL_IN_BLANK":
            blanks = answer.get("blanks", [])
            if isinstance(blanks, list):
                valid = [str(b) for b in blanks if b is not None and str(b).strip()]
                return "\n".join(valid) if valid else None
        elif q_type == "JUDGMENT":
            is_correct = answer.get("isCorrect")
            if is_correct is not None:
                return "正确" if is_correct else "错误"
        else:
            other = answer.get("otherText")
            if other is not None:
                return str(other)
        return None

    async def _update_balances(self) -> None:
        for token in self._tokens:
            self._balance[token] = await self._get_balance(token)

    @staticmethod
    async def _get_balance(token: str) -> int:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }
        try:
            async with httpx.AsyncClient(verify=False, timeout=30) as client:
                resp = await client.get(BALANCE_API, headers=headers)
            if resp.status_code == 200:
                return int(resp.json().get("balance", 0))
        except Exception:
            pass
        return 0


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes")
    return bool(value)
