"""TikuAdapter (开源适配器) provider — https://github.com/DokiDoki1103/tikuAdapter."""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

import httpx

from .base import BaseTikuProvider, TikuQueryInfo

logger = logging.getLogger(__name__)

_TYPE_MAP = {
    "single": 0,
    "multiple": 1,
    "completion": 2,
    "judgement": 3,
    "shortanswer": 4,
}


class TikuAdapter(BaseTikuProvider):
    name = "TikuAdapter题库"

    def __init__(self) -> None:
        self._api_url: str = ""

    async def init(self, config: dict[str, Any]) -> None:
        self._api_url = config.get("url", "")

    async def _query(self, q_info: TikuQueryInfo) -> Optional[str]:
        if not self._api_url:
            logger.error("%s: no API URL configured", self.name)
            return None

        q_type = _TYPE_MAP.get(q_info.question_type, 4)
        # Strip leading letter prefixes from options (e.g. "A. 答案" → "答案")
        cleaned_options = [
            re.sub(r"^[A-Za-z]\.?、?\s?", "", opt) for opt in q_info.options
        ]

        payload = {
            "question": q_info.title,
            "options": cleaned_options,
            "type": q_type,
        }

        try:
            async with httpx.AsyncClient(verify=False, timeout=30) as client:
                resp = await client.post(self._api_url, json=payload)
        except Exception:
            logger.exception("%s: request failed", self.name)
            return None

        if resp.status_code != 200:
            logger.error("%s: HTTP %d — %s", self.name, resp.status_code, resp.text[:200])
            return None

        try:
            data = resp.json()
        except Exception:
            return None

        best = data.get("answer", {}).get("bestAnswer", [])
        if not best:
            logger.error("%s: no bestAnswer in response", self.name)
            return None

        return "\n".join(str(a) for a in best).strip() or None
