from __future__ import annotations

import logging
import random
import re
from typing import Any

from ..chaoxing.client import ChaoxingClient
from ..chaoxing.constants import StudyResult
from ..tiku import TikuService
from .base_service import BaseService

logger = logging.getLogger(__name__)

# Chaoxing numeric type code → semantic name
_TYPE_CODE_TO_NAME: dict[str, str] = {
    "0": "single",
    "1": "multiple",
    "2": "completion",
    "3": "judgement",
    "4": "shortanswer",
}
_TYPE_NAME_TO_CODE: dict[str, str] = {v: k for k, v in _TYPE_CODE_TO_NAME.items()}


class QuizService(BaseService):
    """Process chapter-quiz jobs: fetch questions, look up answers, submit."""

    def __init__(self, session_service, tiku_service: TikuService | None = None):
        super().__init__(session_service)
        self.tiku_service = tiku_service

    def _get_client(self, account_id: str) -> ChaoxingClient:
        return ChaoxingClient(
            account_id=account_id,
            session_manager=self.session_service.session_manager,
        )

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    async def process(self, course, job, job_info, **kwargs):
        work_id = job_info.get("workid") or job_info.get("work_id")
        if not work_id:
            return StudyResult.FAILED

        client = self._get_client(course["account_id"])
        try:
            quiz_payload = await client.get_quiz_questions(
                work_id=work_id,
                jobid=job["jobid"],
                course_id=course.get("course_id") or course.get("courseId", ""),
                clazz_id=course.get("clazz_id") or course.get("clazzId", ""),
                knowledgeid=job_info.get("knowledgeid", ""),
                ktoken=job_info.get("ktoken", ""),
                cpi=job_info.get("cpi", ""),
                enc=job.get("enc", ""),
            )

            if isinstance(quiz_payload, dict):
                questions = quiz_payload.get("questions", [])
                submission_payload: dict[str, Any] = {
                    k: v for k, v in quiz_payload.items() if k != "questions"
                }
            else:
                questions = quiz_payload
                submission_payload = {}

            if not questions:
                return StudyResult.SUCCESS

            answers, found_count = await self._process_questions(questions)
            submission_payload.update(answers)

            # Determine submit / save-only flag based on coverage
            total = len(questions)
            cover_rate = found_count / total if total else 0
            py_flag = self._decide_submit_flag(cover_rate)
            submission_payload["pyFlag"] = py_flag

            if py_flag == "":
                logger.info(
                    "Quiz coverage %.0f%% (>= %.0f%%) — submitting",
                    cover_rate * 100,
                    (self.tiku_service.cover_rate if self.tiku_service else 0.8) * 100,
                )
            else:
                logger.info(
                    "Quiz coverage %.0f%% — saving only (not submitting)",
                    cover_rate * 100,
                )

            success = await client.submit_quiz_answers(submission_payload)
        except Exception:
            logger.exception("Quiz processing failed")
            return StudyResult.FAILED
        return StudyResult.SUCCESS if success else StudyResult.FAILED

    def _decide_submit_flag(self, cover_rate: float) -> str:
        """Return '' to submit, '1' to save-only."""
        if self.tiku_service is None:
            return ""
        # If auto_submit is off in tiku_service, always save-only
        if not self.tiku_service.auto_submit:
            return "1"
        threshold = self.tiku_service.cover_rate
        return "" if cover_rate >= threshold else "1"

    # ------------------------------------------------------------------
    # Question processing
    # ------------------------------------------------------------------

    async def _process_questions(
        self, questions: list[dict[str, Any]]
    ) -> tuple[dict[str, Any], int]:
        """Process all questions. Returns (answer_fields, found_count)."""
        answers: dict[str, Any] = {}
        found_count = 0

        for question in questions:
            q_type_code = self._normalise_type_to_code(question.get("type", "0"))
            q_type_name = _TYPE_CODE_TO_NAME.get(q_type_code, "shortanswer")
            options: list[str] = question.get("options", [])
            answer_fields = question.get("answerField", {})

            answer_key = next(
                (
                    k
                    for k in answer_fields
                    if k.startswith("answer") and not k.startswith("answertype")
                ),
                f"answer{question.get('id', '')}",
            )
            type_key = next(
                (k for k in answer_fields if k.startswith("answertype")),
                f"answertype{question.get('id', '')}",
            )

            # Ask tiku for an answer
            tiku_result = await self._get_answer_from_tiku(question)
            raw_answer: str | None = tiku_result.answer if tiku_result else None

            if raw_answer:
                found_count += 1

            # Convert the raw provider answer into the format Chaoxing expects
            answer_value = self._format_answer(
                raw_answer, q_type_code, q_type_name, options
            )

            answers[answer_key] = answer_value
            answers[type_key] = q_type_code

        return answers, found_count

    async def _get_answer_from_tiku(self, question: dict[str, Any]):
        """Query tiku service for a question. Returns TikuResult or None."""
        if self.tiku_service is None:
            return None
        try:
            return await self.tiku_service.query(question)
        except Exception:
            logger.debug("Tiku query failed", exc_info=True)
            return None

    # ------------------------------------------------------------------
    # Answer formatting — convert raw tiku answer to Chaoxing fields
    # ------------------------------------------------------------------

    def _format_answer(
        self,
        raw_answer: str | None,
        q_type_code: str,
        q_type_name: str,
        options: list[str],
    ) -> str:
        """Convert raw provider answer to the value for Chaoxing submission."""

        if q_type_code == "0":
            # Single choice → letter(s)
            if raw_answer:
                matched = self._match_single_choice(raw_answer, options)
                if matched:
                    return matched
            return self._random_single(len(options))

        if q_type_code == "1":
            # Multiple choice → sorted letters
            if raw_answer:
                matched = self._match_multiple_choice(raw_answer, options)
                if matched:
                    return matched
            return self._random_multiple(len(options))

        if q_type_code == "3":
            # Judgment → "true"/"false"
            if raw_answer and self.tiku_service:
                return "true" if self.tiku_service.judgement_select(raw_answer) else "false"
            return random.choice(["true", "false"])

        if q_type_code == "2":
            # Fill-in-blank
            return raw_answer if raw_answer else "答案"

        # Short answer / other
        return raw_answer if raw_answer else "答案"

    # ------------------------------------------------------------------
    # Answer matching
    # ------------------------------------------------------------------

    def _match_single_choice(self, answer: str, options: list[str]) -> str | None:
        """Match a single answer to options, returning the letter (A/B/C/D)."""
        # If already a single letter
        answer_upper = answer.strip().upper()
        if len(answer_upper) == 1 and answer_upper.isalpha():
            idx = ord(answer_upper) - ord("A")
            if 0 <= idx < len(options):
                return answer_upper

        # Clean the answer of leading letter prefixes
        cleaned = _clean_answer_prefix(answer)
        for idx, option in enumerate(options):
            opt_text = _clean_option_text(option)
            if _is_subsequence(cleaned.lower(), opt_text.lower()):
                return chr(ord("A") + idx)
        return None

    def _match_multiple_choice(self, answer: str, options: list[str]) -> str | None:
        """Match potentially multi-part answer to options, returning sorted letters."""
        # Split the answer on common delimiters
        parts = _multi_split(answer)
        if not parts:
            return None

        matched_letters: set[str] = set()
        for part in parts:
            cleaned = _clean_answer_prefix(part)
            if not cleaned:
                continue

            # Check if it's already a letter
            if len(cleaned) == 1 and cleaned.upper().isalpha():
                idx = ord(cleaned.upper()) - ord("A")
                if 0 <= idx < len(options):
                    matched_letters.add(cleaned.upper())
                    continue

            for idx, option in enumerate(options):
                opt_text = _clean_option_text(option)
                if _is_subsequence(cleaned.lower(), opt_text.lower()):
                    matched_letters.add(chr(ord("A") + idx))
                    break

        return "".join(sorted(matched_letters)) if matched_letters else None

    # ------------------------------------------------------------------
    # Random answer generators
    # ------------------------------------------------------------------

    @staticmethod
    def _random_single(option_count: int) -> str:
        return chr(ord("A") + random.randint(0, max(option_count - 1, 0)))

    @staticmethod
    def _random_multiple(option_count: int) -> str:
        if option_count == 0:
            return "A"
        count = random.randint(1, min(3, option_count))
        selected = random.sample(range(option_count), count)
        return "".join(chr(ord("A") + i) for i in sorted(selected))

    # ------------------------------------------------------------------
    # Type normalisation
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_type_to_code(raw: str) -> str:
        """Convert a type value to numeric code ('0'..'4')."""
        code = _TYPE_NAME_TO_CODE.get(raw)
        if code is not None:
            return code
        return raw if raw in _TYPE_CODE_TO_NAME else "4"


# ---------------------------------------------------------------------------
# Module-level utility functions (ported from legacy)
# ---------------------------------------------------------------------------

def _clean_answer_prefix(text: str) -> str:
    """Remove leading letter + punctuation: 'A. 答案' → '答案'."""
    text = text.strip()
    if len(text) > 1:
        return re.sub(r"^[A-Za-z][.。、,，:：\s]?\s*", "", text)
    return text


def _clean_option_text(option: str) -> str:
    """Strip HTML and leading letter prefix from an option."""
    text = re.sub(r"<[^>]+>", "", str(option)).strip()
    return text


def _is_subsequence(needle: str, haystack: str) -> bool:
    """Check if all chars of *needle* appear in *haystack* in order."""
    it = iter(haystack)
    return all(c in it for c in needle)


def _multi_split(text: str) -> list[str]:
    """Split an answer string using common delimiters (legacy multi_cut)."""
    delimiters = ["\n", ",", "，", "|", "\r", "\t", "#", "、"]
    for delim in delimiters:
        if delim in text:
            return [p.strip() for p in text.split(delim) if p.strip()]
    return [text.strip()] if text.strip() else []
