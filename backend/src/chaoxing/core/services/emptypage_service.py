from __future__ import annotations

from ..chaoxing.client import ChaoxingClient
from ..chaoxing.constants import StudyResult
from .base_service import BaseService


class EmptyPageService(BaseService):
    def _get_client(self, account_id: str) -> ChaoxingClient:
        return ChaoxingClient(
            account_id=account_id,
            session_manager=self.session_service.session_manager,
        )

    async def process(self, course, job, job_info, **kwargs):
        client = self._get_client(course["account_id"])
        success = await client.mark_emptypage_complete(
            course_id=course.get("courseId") or course.get("course_id", ""),
            clazz_id=course.get("clazzId") or course.get("clazz_id", ""),
            chapter_id=job_info.get("knowledgeid") or job_info.get("chapterId", ""),
            cpi=course.get("cpi") or job_info.get("cpi", ""),
        )
        return StudyResult.SUCCESS if success else StudyResult.FAILED
