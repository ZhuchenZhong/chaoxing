from __future__ import annotations

from typing import Any

from ..chaoxing.constants import StudyResult
from ..tiku import TikuService
from .auth_service import AuthService
from .book_service import BookService
from .course_service import CourseService
from .document_service import DocumentService
from .embedded_media_service import EmbeddedMediaService
from .emptypage_service import EmptyPageService
from .image_service import ImageService
from .quiz_service import QuizService
from .reading_service import ReadingService
from .unsupported_service import UnsupportedService
from .video_service import VideoService


class TaskOrchestrator:
    def __init__(self, session_service, tiku_service: TikuService | None = None):
        self.session_service = session_service
        self.auth_service = AuthService(session_service)
        self.course_service = CourseService(session_service)
        self.video_service = VideoService(session_service)
        self.quiz_service = QuizService(session_service, tiku_service)
        self.document_service = DocumentService(session_service)
        self.reading_service = ReadingService(session_service)
        self.emptypage_service = EmptyPageService(session_service)
        self.image_service = ImageService(session_service)
        self.book_service = BookService(session_service)
        self.embedded_media_service = EmbeddedMediaService(session_service)
        self.unsupported_service = UnsupportedService(session_service)

    async def process_job(self, course: dict, job: dict, job_info: dict, **kwargs) -> StudyResult:
        job_type = job.get("type", "").lower() if job.get("type") else ""
        if not job_type and job.get("jobid"):
            job_type = "emptypage"

        try:
            if job_type in ["video", "audio"]:
                return await self.video_service.process(course, job, job_info, **kwargs)
            if job_type in ["workid", "work"]:
                return await self.quiz_service.process(course, job, job_info, **kwargs)
            if job_type in ["document", "doc"]:
                return await self.document_service.process(course, job, job_info, **kwargs)
            if job_type in ["read", "reading"]:
                return await self.reading_service.process(course, job, job_info, **kwargs)
            if job_type in ["emptypage", "empty"]:
                return await self.emptypage_service.process(course, job, job_info, **kwargs)
            if job_type == "insertimage":
                return await self.image_service.process(course, job, job_info, **kwargs)
            if job_type == "insertbook":
                return await self.book_service.process(course, job, job_info, **kwargs)
            if job_type in ["insertaudio", "insertvideo"]:
                return await self.embedded_media_service.process(course, job, job_info, **kwargs)
            if job_type in ["vote", "questionnaire", "group", "discuss", "live"]:
                return await self.unsupported_service.process(course, job, job_info, **kwargs)
            # Unknown job type — skip gracefully
            return StudyResult.SKIPPED
        except Exception:
            return StudyResult.FAILED

    async def login_account(
        self, account_id: str, account: dict[str, str], login_with_cookies: bool = False
    ) -> dict[str, Any]:
        return await self.auth_service.login(account_id, account, login_with_cookies)

    async def get_account_courses(self, account_id: str) -> list[dict[str, Any]]:
        return await self.course_service.get_course_list(account_id)

    async def get_course_points(
        self, account_id: str, course: dict[str, Any]
    ) -> list[dict[str, Any]]:
        return await self.course_service.get_course_points(account_id, course)

    async def get_course_jobs(
        self,
        account_id: str,
        course: dict[str, Any],
        point: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        return await self.course_service.get_course_jobs(account_id, course, point)
