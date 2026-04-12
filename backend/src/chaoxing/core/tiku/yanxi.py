"""TikuYanxi (言溪题库) provider — REST API at https://tk.enncy.cn/query."""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from .base import BaseTikuProvider, TikuQueryInfo

logger = logging.getLogger(__name__)


class TikuYanxi(BaseTikuProvider):
    name = "言溪题库"

    def __init__(self) -> None:
        self.api = "https://tk.enncy.cn/query"
        self._tokens: list[str] = []
        self._token_index: int = 0
        self._times: int = 100

    async def init(self, config: dict[str, Any]) -> None:
        tokens_raw = config.get("tokens", "")
        self._tokens = [t.strip() for t in tokens_raw.split(",") if t.strip()]
        if self._tokens:
            self._token_index = 0

    @property
    def _current_token(self) -> str | None:
        if not self._tokens or self._token_index >= len(self._tokens):
            return None
        return self._tokens[self._token_index]

    def _rotate_token(self) -> bool:
        """Advance to next token. Return False if exhausted."""
        self._token_index += 1
        self._times = 100
        return self._token_index < len(self._tokens)

    async def _query(self, q_info: TikuQueryInfo) -> Optional[str]:
        token = self._current_token
        if not token:
            logger.error("%s: no available tokens", self.name)
            return None

        async with httpx.AsyncClient(verify=False, timeout=30) as client:
            resp = await client.get(
                self.api,
                params={"question": q_info.title, "token": token},
            )

        if resp.status_code != 200:
            logger.error("%s query failed: %s", self.name, resp.text[:200])
            return None

        data = resp.json()
        if not data.get("code"):
            answer_text = data.get("data", {}).get("answer", "")
            if self._times == 0 or "次数不足" in answer_text:
                logger.info("%s: token exhausted, rotating", self.name)
                if self._rotate_token():
                    return await self._query(q_info)
                return None
            logger.error(
                "%s query failed: %s",
                self.name,
                data.get("message", "unknown"),
            )
            return None

        self._times = data.get("data", {}).get("times", self._times)
        return data["data"]["answer"].strip() or None
