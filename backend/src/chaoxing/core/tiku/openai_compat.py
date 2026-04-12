"""OpenAI-compatible LLM provider for quiz answering."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any, Optional

import httpx

from .base import BaseTikuProvider, TikuQueryInfo

logger = logging.getLogger(__name__)

# System prompts per question type (ported from legacy AI class)
_SYSTEM_PROMPTS = {
    "single": (
        "本题为单选题，你只能选择一个选项，请根据题目和选项回答问题，"
        '以json格式输出正确的选项内容，示例回答：{"Answer": ["答案"]}。'
        "除此之外不要输出任何多余的内容，也不要使用MD语法。"
        "如果你使用了互联网搜索，也请不要返回搜索的结果和参考资料"
    ),
    "multiple": (
        "本题为多选题，你必须选择两个或以上选项，请根据题目和选项回答问题，"
        '以json格式输出正确的选项内容，示例回答：{"Answer": ["答案1",\n"答案2",\n"答案3"]}。'
        "除此之外不要输出任何多余的内容，也不要使用MD语法。"
        "如果你使用了互联网搜索，也请不要返回搜索的结果和参考资料"
    ),
    "completion": (
        "本题为填空题，你必须根据语境和相关知识填入合适的内容，"
        '请根据题目回答问题，以json格式输出正确的答案，示例回答：{"Answer": ["答案"]}。'
        "除此之外不要输出任何多余的内容，也不要使用MD语法。"
        "如果你使用了互联网搜索，也请不要返回搜索的结果和参考资料"
    ),
    "judgement": (
        "本题为判断题，你只能回答正确或者错误，"
        '请根据题目回答问题，以json格式输出正确的答案，示例回答：{"Answer": ["正确"]}。'
        "除此之外不要输出任何多余的内容，也不要使用MD语法。"
        "如果你使用了互联网搜索，也请不要返回搜索的结果和参考资料"
    ),
    "shortanswer": (
        "本题为简答题，你必须根据语境和相关知识填入合适的内容，"
        '请根据题目回答问题，以json格式输出正确的答案，示例回答：{"Answer": ["这是我的答案"]}。'
        "除此之外不要输出任何多余的内容，也不要使用MD语法。"
        "如果你使用了互联网搜索，也请不要返回搜索的结果和参考资料"
    ),
}


def _remove_md_json_wrapper(text: str) -> str:
    """Strip Markdown code-block wrappers around JSON."""
    match = re.search(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", text, re.DOTALL)
    return match.group(1).strip() if match else text.strip()


class OpenAICompatProvider(BaseTikuProvider):
    name = "AI大模型答题"

    def __init__(self) -> None:
        self._endpoint: str = "https://api.openai.com/v1"
        self._key: str = ""
        self._model: str = "gpt-4"
        self._http_proxy: str | None = None
        self._min_interval: float = 1.0
        self._last_request_time: float = 0

    async def init(self, config: dict[str, Any]) -> None:
        self._endpoint = config.get("endpoint", self._endpoint).rstrip("/")
        self._key = config.get("key", "")
        self._model = config.get("model", self._model)
        self._http_proxy = config.get("http_proxy") or None
        self._min_interval = float(config.get("min_interval_seconds", 1))

    async def _query(self, q_info: TikuQueryInfo) -> Optional[str]:
        await self._rate_limit()

        system_prompt = _SYSTEM_PROMPTS.get(q_info.question_type, _SYSTEM_PROMPTS["shortanswer"])
        user_content = f"题目：{q_info.title}"
        if q_info.question_type in ("single", "multiple") and q_info.options:
            # Strip leading letter prefixes to prevent LLM from just echoing A/B/C/D
            cleaned = [re.sub(r"^[A-Z]\s*", "", opt) for opt in q_info.options]
            user_content += f"\n选项：{chr(10).join(cleaned)}"

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        }

        headers = {
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(
                verify=False,
                timeout=60,
                proxy=self._http_proxy,
            ) as client:
                resp = await client.post(
                    f"{self._endpoint}/chat/completions",
                    json=payload,
                    headers=headers,
                )
            self._last_request_time = time.monotonic()
        except Exception:
            logger.exception("%s: API request failed", self.name)
            return None

        if resp.status_code != 200:
            logger.error("%s: HTTP %d — %s", self.name, resp.status_code, resp.text[:300])
            return None

        return self._parse_response(resp)

    def _parse_response(self, resp: httpx.Response) -> str | None:
        try:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(_remove_md_json_wrapper(content))
            answers = parsed["Answer"]
            return "\n".join(str(a) for a in answers).strip() or None
        except Exception:
            logger.exception("%s: failed to parse LLM response", self.name)
            return None

    async def _rate_limit(self) -> None:
        if self._last_request_time:
            elapsed = time.monotonic() - self._last_request_time
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)

    async def check_connection(self) -> bool:
        headers = {
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": "1+1=?"}],
            "max_tokens": 10,
        }
        try:
            async with httpx.AsyncClient(
                verify=False,
                timeout=30,
                proxy=self._http_proxy,
            ) as client:
                resp = await client.post(
                    f"{self._endpoint}/chat/completions",
                    json=payload,
                    headers=headers,
                )
            return resp.status_code == 200
        except Exception:
            return False
