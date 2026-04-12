"""SiliconFlow (硅基流动/DeepSeek) provider for quiz answering."""

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

_DEFAULT_ENDPOINT = "https://api.siliconflow.cn/v1/chat/completions"
_DEFAULT_MODEL = "deepseek-ai/DeepSeek-V3"

_SYSTEM_PROMPTS = {
    "single": (
        "本题为单选题，请根据题目和选项选择唯一正确答案，输出的是选项的具体内容，"
        '而不是内容前的ABCD，并以JSON格式输出：示例回答：{"Answer": ["正确选项内容"]}。'
        "除此之外不要输出任何多余的内容，也不要使用MD语法。"
        "如果你使用了互联网搜索，也请不要返回搜索的结果和参考资料"
    ),
    "multiple": (
        "本题为多选题，请选择所有正确选项，输出的是选项的具体内容，"
        '而不是内容前的ABCD，以JSON格式输出：示例回答：{"Answer": ["选项1","选项2"]}。'
        "除此之外不要输出任何多余的内容，也不要使用MD语法。"
        "如果你使用了互联网搜索，也请不要返回搜索的结果和参考资料"
    ),
    "completion": (
        "本题为填空题，请直接给出填空内容，"
        '以JSON格式输出：示例回答：{"Answer": ["答案文本"]}。'
        "除此之外不要输出任何多余的内容，也不要使用MD语法。"
        "如果你使用了互联网搜索，也请不要返回搜索的结果和参考资料"
    ),
    "judgement": (
        "本题为判断题，请回答'正确'或'错误'，"
        '以JSON格式输出：示例回答：{"Answer": ["正确"]}。'
        "除此之外不要输出任何多余的内容，也不要使用MD语法。"
        "如果你使用了互联网搜索，也请不要返回搜索的结果和参考资料"
    ),
    "shortanswer": (
        "本题为简答题，请根据语境和相关知识给出答案，"
        '以JSON格式输出：示例回答：{"Answer": ["这是我的答案"]}。'
        "除此之外不要输出任何多余的内容，也不要使用MD语法。"
        "如果你使用了互联网搜索，也请不要返回搜索的结果和参考资料"
    ),
}


def _remove_md_json_wrapper(text: str) -> str:
    match = re.search(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", text, re.DOTALL)
    return match.group(1).strip() if match else text.strip()


class SiliconFlowProvider(BaseTikuProvider):
    name = "硅基流动大模型"

    def __init__(self) -> None:
        self._endpoint: str = _DEFAULT_ENDPOINT
        self._key: str = ""
        self._model: str = _DEFAULT_MODEL
        self._min_interval: float = 3.0
        self._last_request_time: float = 0

    async def init(self, config: dict[str, Any]) -> None:
        self._endpoint = config.get("siliconflow_endpoint", _DEFAULT_ENDPOINT)
        self._key = config.get("siliconflow_key", "")
        self._model = config.get("siliconflow_model", _DEFAULT_MODEL)
        self._min_interval = float(config.get("min_interval_seconds", 3))

    async def _query(self, q_info: TikuQueryInfo) -> Optional[str]:
        await self._rate_limit()

        system_prompt = _SYSTEM_PROMPTS.get(q_info.question_type, _SYSTEM_PROMPTS["shortanswer"])
        user_content = f"题目：{q_info.title}\n选项：{', '.join(q_info.options)}"

        headers = {
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "stream": False,
            "max_tokens": 4096,
            "temperature": 0.7,
            "top_p": 0.7,
            "response_format": {"type": "text"},
        }

        try:
            async with httpx.AsyncClient(verify=False, timeout=30) as client:
                resp = await client.post(self._endpoint, json=payload, headers=headers)
            self._last_request_time = time.monotonic()
        except Exception:
            logger.exception("%s: API request failed", self.name)
            return None

        if resp.status_code != 200:
            logger.error("%s: HTTP %d — %s", self.name, resp.status_code, resp.text[:300])
            return None

        try:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(_remove_md_json_wrapper(content))
            return "\n".join(str(a) for a in parsed["Answer"]).strip() or None
        except Exception:
            logger.exception("%s: failed to parse response", self.name)
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
            "stream": False,
            "max_tokens": 10,
            "temperature": 0.7,
            "top_p": 0.7,
            "response_format": {"type": "text"},
        }
        try:
            async with httpx.AsyncClient(verify=False, timeout=30) as client:
                resp = await client.post(self._endpoint, json=payload, headers=headers)
            return resp.status_code == 200
        except Exception:
            return False
