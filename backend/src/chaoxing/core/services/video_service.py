from __future__ import annotations

import asyncio
import hashlib
import time

from ..chaoxing.client import ChaoxingClient
from ..chaoxing.constants import StudyResult
from .base_service import BaseService


class VideoService(BaseService):
    def _get_client(self, account_id: str) -> ChaoxingClient:
        return ChaoxingClient(
            account_id=account_id,
            session_manager=self.session_service.session_manager,
        )

    async def process(self, course, job, job_info, speed: float = 1.0, **kwargs):
        dtoken = job_info.get("dtoken")
        duration = job_info.get("duration", 0)
        object_id = job_info.get("objectid")
        if not all([dtoken, duration, object_id]):
            return StudyResult.FAILED

        client = self._get_client(course["account_id"])
        try:
            current_progress = await client.get_video_progress(course["course_id"], dtoken)
            if current_progress.get("isPassed"):
                return StudyResult.SUCCESS

            await self._simulate_video_watching(client, course, job, job_info, duration, speed)
            final_progress = await client.get_video_progress(course["course_id"], dtoken)
            return StudyResult.SUCCESS if final_progress.get("isPassed") else StudyResult.FAILED
        except Exception as exc:
            if getattr(exc, "status_code", None) == 403:
                await self._handle_forbidden_error()
                return StudyResult.FAILED
            raise

    async def _simulate_video_watching(
        self,
        client: ChaoxingClient,
        course,
        job,
        job_info,
        duration: int,
        speed: float,
    ) -> None:
        play_time = max(60, int(duration / max(speed, 0.1)))
        log_interval = max(1, min(play_time // 10, 30))

        for current_time in range(0, play_time, log_interval):
            current_time = min(current_time, duration - 1)
            enc = self._generate_enc(course, job, job_info, current_time, duration)
            await client.log_video_progress(
                course_id=course.get("course_id") or course.get("courseId"),
                clazz_id=course.get("clazz_id") or course.get("clazzId"),
                cpi=course.get("cpi") or job_info.get("cpi", ""),
                dtoken=job_info["dtoken"],
                playing_time=current_time,
                duration=duration,
                jobid=job["jobid"],
                objectid=job_info.get("objectid") or job.get("objectid", ""),
                otherinfo=job.get("otherinfo", ""),
                enc=enc,
                dtype="Audio" if job.get("type") == "audio" else "Video",
                rt=job.get("rt", ""),
                video_face_capture_enc=job.get("videoFaceCaptureEnc", ""),
                att_duration=job.get("attDuration", ""),
                att_duration_enc=job.get("attDurationEnc", ""),
            )
            if current_time % 60 == 0:
                await client.refresh_video_status(job_info["objectid"])

    def _generate_enc(self, course, job, job_info, current_time: int, total_time: int) -> str:
        clazz_id = course.get("clazz_id") or course.get("clazzId", "")
        userid = course.get("userid", "")
        jobid = job.get("jobid", "")
        object_id = job_info.get("objectid") or job.get("objectid", "")
        raw = (
            f"[{clazz_id}][{userid}][{jobid}][{object_id}]"
            f"[{current_time * 1000}][d_yHJ!$pdA~5]"
            f"[{total_time * 1000}][0_{total_time}]"
        )
        return hashlib.md5(raw.encode()).hexdigest()

    async def _handle_forbidden_error(self) -> None:
        await asyncio.sleep(0)
