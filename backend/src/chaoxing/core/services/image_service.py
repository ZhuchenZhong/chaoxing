from __future__ import annotations

from ..chaoxing.client import ChaoxingClient
from ..chaoxing.constants import StudyResult
from .base_service import BaseService


class ImageService(BaseService):
    def _get_client(self, account_id: str) -> ChaoxingClient:
        return ChaoxingClient(
            account_id=account_id,
            session_manager=self.session_service.session_manager,
        )

    async def process(self, course, job, job_info, **kwargs):
        try:
            client = self._get_client(course["account_id"])
            success = await client.mark_page_viewed(
                course_id=course.get("course_id"),
                knowledgeid=job_info.get("knowledgeid"),
                jobid=job["jobid"],
            )
        except Exception:
            return StudyResult.FAILED
        return StudyResult.SUCCESS if success else StudyResult.FAILED
