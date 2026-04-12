from __future__ import annotations

import re

from ..chaoxing.client import ChaoxingClient
from ..chaoxing.constants import StudyResult
from .base_service import BaseService


class DocumentService(BaseService):
    def _get_client(self, account_id: str) -> ChaoxingClient:
        return ChaoxingClient(
            account_id=account_id,
            session_manager=self.session_service.session_manager,
        )

    async def process(self, course, job, job_info, **kwargs):
        # Extract knowledgeid (nodeId) from otherinfo, matching legacy regex
        otherinfo = job.get("otherinfo", "")
        node_match = re.findall(r"nodeId_(.*?)-", otherinfo)
        knowledgeid = node_match[0] if node_match else job_info.get("knowledgeid", "")

        client = self._get_client(course["account_id"])
        success = await client.mark_document_complete(
            jobid=job["jobid"],
            knowledgeid=knowledgeid,
            course_id=course.get("courseId") or course.get("course_id", ""),
            clazz_id=course.get("clazzId") or course.get("clazz_id", ""),
            jtoken=job.get("jtoken", ""),
        )
        return StudyResult.SUCCESS if success else StudyResult.FAILED
