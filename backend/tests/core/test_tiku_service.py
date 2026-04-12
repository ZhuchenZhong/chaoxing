"""Tests for TikuService — fallback chain, caching, answer validation."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from chaoxing.core.tiku.base import (
    BaseTikuProvider,
    TikuQueryInfo,
    TikuResult,
    check_answer,
    check_judgement,
    split_answer,
)
from chaoxing.core.tiku.service import TikuService


# ---------------------------------------------------------------------------
# TikuQueryInfo
# ---------------------------------------------------------------------------


def test_tiku_query_info_from_question_normalises():
    q = TikuQueryInfo.from_question({
        "type": "0",
        "title": "1.What is Python?（2分）",
        "options": ["A. Language", "B. Snake"],
    })
    assert q.question_type == "single"
    assert q.title == ".What is Python?"  # stripped numbering and point values
    assert q.options == ["A. Language", "B. Snake"]


def test_tiku_query_info_strips_html():
    q = TikuQueryInfo.from_question({"type": "1", "title": "<p>Bold <b>question</b>?</p>"})
    assert q.question_type == "multiple"
    assert q.title == "Bold question?"


def test_tiku_query_info_unknown_type_defaults_to_shortanswer():
    q = TikuQueryInfo.from_question({"type": "99", "title": "test"})
    assert q.question_type == "shortanswer"


# ---------------------------------------------------------------------------
# split_answer
# ---------------------------------------------------------------------------


def test_split_answer_with_newline():
    assert split_answer("A\nB\nC") == ["A", "B", "C"]


def test_split_answer_with_chinese_comma():
    assert split_answer("选项A，选项B") == ["选项A", "选项B"]


def test_split_answer_single_value():
    assert split_answer("ABC") == ["ABC"]


def test_split_answer_none():
    assert split_answer(None) is None


def test_split_answer_empty():
    assert split_answer("") is None


# ---------------------------------------------------------------------------
# check_judgement
# ---------------------------------------------------------------------------


def test_check_judgement_true():
    assert check_judgement("正确", ["正确", "对"], ["错误", "错"]) == 1
    assert check_judgement("T", ["T", "true"], ["F", "false"]) == 1


def test_check_judgement_false():
    assert check_judgement("错误", ["正确"], ["错误"]) == 0


def test_check_judgement_unknown():
    assert check_judgement("maybe", ["yes"], ["no"]) == -1


# ---------------------------------------------------------------------------
# check_answer
# ---------------------------------------------------------------------------


def test_check_answer_single_choice():
    assert check_answer("A", "single", ["正确"], ["错误"]) is True
    # Multiple answers should fail for single choice
    assert check_answer("A\nB", "single", ["正确"], ["错误"]) is False


def test_check_answer_multiple_choice():
    assert check_answer("A\nB", "multiple", ["正确"], ["错误"]) is True


def test_check_answer_completion():
    assert check_answer("some text", "completion", [], []) is True
    assert check_answer("", "completion", [], []) is False


def test_check_answer_judgement():
    assert check_answer("正确", "judgement", ["正确"], ["错误"]) is True
    assert check_answer("maybe", "judgement", ["正确"], ["错误"]) is False


# ---------------------------------------------------------------------------
# TikuService — fallback chain
# ---------------------------------------------------------------------------


class FakeTikuProvider(BaseTikuProvider):
    def __init__(self, name: str, answer: str | None):
        self.name = name
        self._answer = answer

    async def _query(self, q_info: TikuQueryInfo):
        return self._answer


@pytest.mark.asyncio
async def test_tiku_service_returns_first_valid_answer():
    service = TikuService()
    service._providers = [
        FakeTikuProvider("empty", None),
        FakeTikuProvider("good", "A"),
    ]

    result = await service.query({"type": "0", "title": "What is 1+1?", "options": ["A", "B"]})

    assert result is not None
    assert result.answer == "A"
    assert result.provider_name == "good"
    assert result.from_cache is False


@pytest.mark.asyncio
async def test_tiku_service_returns_none_when_all_fail():
    service = TikuService()
    service._providers = [
        FakeTikuProvider("fail1", None),
        FakeTikuProvider("fail2", ""),
    ]

    result = await service.query({"type": "0", "title": "Unknown?", "options": ["A"]})
    assert result is None


@pytest.mark.asyncio
async def test_tiku_service_caches_result_in_memory():
    service = TikuService()
    provider = FakeTikuProvider("test", "B")
    service._providers = [provider]

    # First query — hits provider
    result1 = await service.query({"type": "0", "title": "Cache test?", "options": ["A", "B"]})
    assert result1 is not None
    assert result1.provider_name == "test"
    assert result1.from_cache is False

    # Second query — should hit cache
    result2 = await service.query({"type": "0", "title": "Cache test?", "options": ["A", "B"]})
    assert result2 is not None
    assert result2.provider_name == "cache"
    assert result2.from_cache is True
    assert result2.answer == "B"


@pytest.mark.asyncio
async def test_tiku_service_skips_type_mismatched_answer():
    """A single-choice question should reject a true/false answer."""
    service = TikuService()
    # Provider returns "正确" which is a judgement answer, not valid for single-choice
    service._providers = [
        FakeTikuProvider("wrong_type", "正确"),
        FakeTikuProvider("correct", "A"),
    ]

    result = await service.query({"type": "0", "title": "Pick one?", "options": ["A", "B"]})
    assert result is not None
    assert result.provider_name == "correct"
    assert result.answer == "A"


@pytest.mark.asyncio
async def test_tiku_service_returns_none_for_empty_title():
    service = TikuService()
    service._providers = [FakeTikuProvider("test", "A")]

    result = await service.query({"type": "0", "title": "", "options": ["A"]})
    assert result is None


@pytest.mark.asyncio
async def test_tiku_service_handles_provider_exception():
    """If a provider raises, service should continue to next provider."""
    service = TikuService()

    class FailProvider(BaseTikuProvider):
        name = "crasher"

        async def _query(self, q_info):
            raise RuntimeError("API down")

    service._providers = [
        FailProvider(),
        FakeTikuProvider("fallback", "C"),
    ]

    result = await service.query({"type": "0", "title": "Crash test?", "options": ["A", "C"]})
    assert result is not None
    assert result.provider_name == "fallback"


# ---------------------------------------------------------------------------
# Judgement helper
# ---------------------------------------------------------------------------


def test_judgement_select_true():
    service = TikuService()
    assert service.judgement_select("正确") is True
    assert service.judgement_select("T") is True


def test_judgement_select_false():
    service = TikuService()
    assert service.judgement_select("错误") is False
    assert service.judgement_select("F") is False


def test_get_submit_flag():
    assert TikuService(auto_submit=True).get_submit_flag() == ""
    assert TikuService(auto_submit=False).get_submit_flag() == "1"
