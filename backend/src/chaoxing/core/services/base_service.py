from __future__ import annotations

from ..chaoxing.constants import StudyResult


class BaseService:
    def __init__(self, session_service):
        self.session_service = session_service

    async def process(self, course, job, job_info, **kwargs):
        return StudyResult.FAILED
