from __future__ import annotations

from ..chaoxing.constants import StudyResult
from .base_service import BaseService


class UnsupportedService(BaseService):
    async def process(self, course, job, job_info, **kwargs):
        return StudyResult.SKIPPED
