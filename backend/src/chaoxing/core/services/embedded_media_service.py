from __future__ import annotations

from ..chaoxing.client import ChaoxingClient
from ..chaoxing.constants import StudyResult
from .base_service import BaseService


class EmbeddedMediaService(BaseService):
    def _get_client(self, account_id: str) -> ChaoxingClient:
        return ChaoxingClient(
            account_id=account_id,
            session_manager=self.session_service.session_manager,
        )

    async def process(self, course, job, job_info, **kwargs):
        account_id = course.get("account_id")
        job_id = job.get("jobid")
        if not account_id or not job_id:
            return StudyResult.FAILED

        try:
            client = self._get_client(account_id)
            success = await client.mark_embedded_media_viewed(
                course_id=course.get("course_id"),
                clazz_id=course.get("clazz_id"),
                job_id=job_id,
                media_id=job_info.get("mediaid"),
                media_type=job.get("type", "insertaudio"),
            )
        except Exception:
            return StudyResult.FAILED
        return StudyResult.SUCCESS if success else StudyResult.FAILED
