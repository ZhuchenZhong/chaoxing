from __future__ import annotations

from typing import Any

from ..chaoxing.client import ChaoxingClient
from .session_service import SessionService


class CourseService:
    def __init__(self, session_service: SessionService):
        self.session_service = session_service

    def _get_client(self, account_id: str) -> ChaoxingClient:
        return ChaoxingClient(
            account_id=account_id, session_manager=self.session_service.session_manager
        )

    async def get_course_list(self, account_id: str) -> list[dict[str, Any]]:
        client = self._get_client(account_id)
        return await client.get_courses()

    async def get_course_points(
        self, account_id: str, course: dict[str, Any]
    ) -> list[dict[str, Any]]:
        client = self._get_client(account_id)
        result = await client.get_course_chapters(
            course_id=course["course_id"], clazz_id=course["clazz_id"], cpi=course["cpi"]
        )
        if isinstance(result, dict) and "chapters" in result:
            return result["chapters"]
        return result if isinstance(result, list) else []

    async def get_course_jobs(
        self,
        account_id: str,
        course: dict[str, Any],
        point: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        client = self._get_client(account_id)
        return await client.get_job_list(
            {
                "courseId": course.get("courseId") or course.get("course_id"),
                "clazzId": course.get("clazzId") or course.get("clazz_id"),
                "cpi": course["cpi"],
            },
            point,
        )
