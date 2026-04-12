from __future__ import annotations

import asyncio
import hashlib
import logging
import random
import re
import time

from ..chaoxing.client import ChaoxingClient
from ..chaoxing.constants import StudyResult
from .base_service import BaseService

logger = logging.getLogger(__name__)

THRESHOLD = 1  # seconds between simulation ticks (matches legacy gc.THRESHOLD)
MAX_FORBIDDEN_RETRY = 2


class VideoService(BaseService):
    def _get_client(self, account_id: str) -> ChaoxingClient:
        return ChaoxingClient(
            account_id=account_id,
            session_manager=self.session_service.session_manager,
        )

    async def process(self, course, job, job_info, speed: float = 1.0, **kwargs):
        """Process a video/audio task point, matching legacy study_video behavior.

        The method first tries dtype="Video"; on failure it retries as "Audio",
        mirroring the legacy fallback logic.
        """
        result = await self._study_media(course, job, job_info, speed, dtype="Video")
        if result != StudyResult.SUCCESS:
            result = await self._study_media(course, job, job_info, speed, dtype="Audio")
        return result

    async def _study_media(
        self, course, job, job_info, speed: float, dtype: str
    ) -> StudyResult:
        client = self._get_client(course["account_id"])

        # Step 1: Fetch video/audio metadata from /ananas/status/{objectid}
        object_id = job.get("objectid", "")
        status_data = await client.refresh_video_status(object_id, dtype=dtype)
        if not status_data:
            return StudyResult.FAILED

        dtoken = status_data["dtoken"]
        duration = int(status_data["duration"])
        if duration <= 0:
            return StudyResult.FAILED

        # Resolve rt parameter (legacy logic)
        rt = job.get("rt") or ""
        if not rt:
            rt_match = re.search(r"-rt_([1d])", job.get("otherinfo", ""))
            if rt_match:
                rt = "0.9" if rt_match.group(1) == "d" else "1"

        play_time = int(job.get("playTime", 0)) // 1000
        userid = await client.get_userid()

        course_id = course.get("courseId") or course.get("course_id", "")
        clazz_id = course.get("clazzId") or course.get("clazz_id", "")
        cpi = course.get("cpi") or job_info.get("cpi", "")

        async def _log_progress(current: int) -> tuple[bool, int]:
            enc = _generate_enc(clazz_id, userid, job.get("jobid", ""), object_id, current, duration)
            return await client.log_video_progress(
                course_id=course_id,
                clazz_id=clazz_id,
                cpi=cpi,
                dtoken=dtoken,
                playing_time=current,
                duration=duration,
                jobid=job.get("jobid", ""),
                objectid=object_id,
                otherinfo=job.get("otherinfo", ""),
                enc=enc,
                dtype=dtype,
                rt=rt or None,
                video_face_capture_enc=job.get("videoFaceCaptureEnc") or None,
                att_duration=job.get("attDuration") or None,
                att_duration_enc=job.get("attDurationEnc") or None,
            )

        # Step 2: Initial progress reports (legacy sends current pos, then full duration)
        passed, _ = await _log_progress(play_time)
        if not passed:
            passed, _ = await _log_progress(duration)
        if passed:
            return StudyResult.SUCCESS

        # Step 3: Simulate playback loop
        last_log_time = 0.0
        last_iter = time.monotonic()
        wait_time = random.uniform(30, 90)
        forbidden_retry = 0

        while not passed:
            if play_time - last_log_time >= wait_time or play_time >= duration:
                passed, status_code = await _log_progress(int(play_time))

                if status_code == 403:
                    if forbidden_retry >= MAX_FORBIDDEN_RETRY:
                        return StudyResult.FAILED
                    forbidden_retry += 1
                    await asyncio.sleep(random.uniform(2, 4))
                    refreshed = await self._recover_after_forbidden(client, object_id, dtype)
                    if refreshed:
                        dtoken = refreshed.get("dtoken", dtoken)
                        duration = int(refreshed.get("duration", duration))
                        play_time = float(refreshed.get("playTime", play_time))
                    continue

                if not passed and status_code != 200:
                    return StudyResult.FAILED

                wait_time = random.uniform(30, 90)
                last_log_time = play_time

            now = time.monotonic()
            dt = (now - last_iter) * speed
            last_iter = now
            play_time = min(duration, play_time + dt)

            await asyncio.sleep(THRESHOLD)

        return StudyResult.SUCCESS

    async def _recover_after_forbidden(
        self, client: ChaoxingClient, object_id: str, dtype: str
    ) -> dict | None:
        """Try to recover session after a 403 (mirrors legacy _recover_after_forbidden)."""
        try:
            return await client.refresh_video_status(object_id, dtype=dtype)
        except Exception:
            return None


def _generate_enc(
    clazz_id: str,
    userid: str,
    jobid: str,
    object_id: str,
    playing_time: int,
    duration: int,
) -> str:
    """Generate enc hash matching the legacy get_enc formula exactly."""
    raw = (
        f"[{clazz_id}][{userid}][{jobid}][{object_id}]"
        f"[{playing_time * 1000}][d_yHJ!$pdA~5]"
        f"[{duration * 1000}][0_{duration}]"
    )
    return hashlib.md5(raw.encode()).hexdigest()
