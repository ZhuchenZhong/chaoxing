"""Celery tasks for study-run execution.

Lifecycle:
  API creates StudyRun (status=QUEUED) → dispatches ``process_study_run`` task
  → login → fetch courses → iterate chapters/jobs → update progress → notify
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from datetime import datetime, timezone
from typing import Any, TypeVar

from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..core.chaoxing.constants import StudyResult
from ..core.chaoxing.crypto import AESCipher
from ..core.chaoxing.rate_limiter import AsyncRateLimiter
from ..core.notification import NotificationService
from ..core.services.session_service import SessionService
from ..core.services.task_orchestrator import TaskOrchestrator
from ..db.database import AsyncSessionLocal
from ..models.chaoxing_account import ChaoxingAccount
from ..models.enums import ChaoxingAuthType
from ..models.notification_config import NotificationConfig
from ..models.study_profile import StudyProfile
from ..models.study_run import StudyRun, StudyRunEvent, StudyRunEventLevel, StudyRunStatus
from .celery_app import celery_app

T = TypeVar("T")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run_async(coroutine: Coroutine[Any, Any, T]) -> T:
    """Run an async coroutine from synchronous Celery task context."""
    if not asyncio.iscoroutine(coroutine):
        raise TypeError("run_async() requires a coroutine object")
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)
    coroutine.close()
    raise RuntimeError(
        "run_async() cannot be called while an event loop is already running; "
        "await the coroutine directly from async code"
    )


def _build_login_payload(account: ChaoxingAccount) -> tuple[dict[str, str], bool]:
    cipher = AESCipher()
    if account.auth_type == ChaoxingAuthType.COOKIES:
        cookies = account.cookies_encrypted or "{}"
        return {"cookies": cipher.decrypt(cookies)}, True
    username = account.username_encrypted or ""
    password = account.password_encrypted or ""
    return {
        "username": cipher.decrypt(username),
        "password": cipher.decrypt(password),
    }, False


async def _append_event(
    session: AsyncSession,
    run_id: int,
    level: StudyRunEventLevel,
    message: str,
    detail_json: dict[str, Any] | None = None,
) -> None:
    session.add(
        StudyRunEvent(
            run_id=run_id,
            level=level,
            message=message,
            detail_json=detail_json or {},
            created_at=datetime.now(timezone.utc),
        )
    )


async def _send_notification(
    session: AsyncSession,
    user_id: int,
    title: str,
    content: str,
) -> None:
    """Load user notification configs and send (best-effort, never blocks the run)."""
    try:
        result = await session.execute(
            select(NotificationConfig).where(NotificationConfig.user_id == user_id)
        )
        configs = list(result.scalars().all())
        if not configs:
            return
        config_dicts = [
            {
                "provider": cfg.provider.value,
                "enabled": cfg.enabled,
                "settings_json": cfg.settings_json,
            }
            for cfg in configs
        ]
        service = NotificationService(config_dicts)
        await service.send_all(title, content)
    except Exception:
        pass


async def _is_run_cancelled(
    session_factory: async_sessionmaker,
    run_id: int,
) -> bool:
    """Check if the run has been cancelled by the user (separate short-lived session)."""
    async with session_factory() as session:
        run = await session.get(StudyRun, run_id)
        if run is None:
            return True
        return run.status in (StudyRunStatus.CANCELLED, StudyRunStatus.STOPPING)


async def _update_progress(
    session: AsyncSession,
    run: StudyRun,
    *,
    total_courses: int,
    processed_courses: int,
    processed_jobs: int,
    successful_jobs: int,
    failed_jobs: int,
    skipped_jobs: int,
) -> None:
    """Persist current progress snapshot."""
    total_jobs = processed_jobs + skipped_jobs
    run.progress_json = {
        "total_courses": total_courses,
        "processed_courses": processed_courses,
        "processed_jobs": processed_jobs,
        "successful_jobs": successful_jobs,
        "failed_jobs": failed_jobs,
        "skipped_jobs": skipped_jobs,
        "progress_pct": round(processed_courses / total_courses * 100, 1) if total_courses else 0,
        "total_job_count": total_jobs,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await session.commit()


# ---------------------------------------------------------------------------
# Core execution logic
# ---------------------------------------------------------------------------


async def process_study_run_job(
    run_id: int,
    *,
    session_factory: async_sessionmaker = AsyncSessionLocal,
    orchestrator_factory=None,
) -> dict[str, Any]:
    """Execute a full study run: login → courses → chapters → jobs."""
    session_service = SessionService()
    orchestrator = (
        orchestrator_factory() if orchestrator_factory is not None else TaskOrchestrator(session_service)
    )

    processed_jobs = 0
    successful_jobs = 0
    failed_jobs = 0
    skipped_jobs = 0
    processed_courses = 0

    try:
        async with session_factory() as session:
            # ── Load run & account ──────────────────────────────────────
            run = await session.get(StudyRun, run_id)
            if run is None:
                raise ValueError(f"Study run {run_id} does not exist")

            account = await session.get(ChaoxingAccount, run.account_id)
            if account is None:
                raise ValueError(f"Chaoxing account {run.account_id} does not exist")

            # Load optional study profile for speed/delay settings
            profile: StudyProfile | None = None
            if run.profile_id:
                profile = await session.get(StudyProfile, run.profile_id)

            speed = float(profile.speed) if profile else 1.0
            job_delay = 0.5  # default delay between jobs (seconds)

            # Mark run as RUNNING
            run.status = StudyRunStatus.RUNNING
            run.started_at = datetime.now(timezone.utc)
            await _append_event(
                session, run.id, StudyRunEventLevel.INFO,
                "Study run started",
                {"course_ids": run.course_ids, "speed": speed},
            )
            await session.commit()

            # ── Login ───────────────────────────────────────────────────
            login_payload, login_with_cookies = _build_login_payload(account)
            login_result = await orchestrator.login_account(
                str(account.id), login_payload, login_with_cookies
            )
            if login_result.get("status") != "success":
                reason = login_result.get("message", "Login failed")
                run.status = StudyRunStatus.FAILED
                run.finished_at = datetime.now(timezone.utc)
                await _append_event(
                    session, run.id, StudyRunEventLevel.ERROR,
                    "Login failed", {"reason": reason},
                )
                await session.commit()
                await _send_notification(
                    session, run.user_id,
                    "学习任务失败 / Study Run Failed",
                    f"任务 #{run.id} 失败: {reason}",
                )
                return {"run_id": run.id, "status": "failed", "message": reason}

            # ── Fetch & filter courses ──────────────────────────────────
            courses = await orchestrator.get_account_courses(str(account.id))
            selected_ids = {str(cid) for cid in run.course_ids}
            selected_courses = [
                c for c in courses
                if str(c.get("courseId") or c.get("id") or "") in selected_ids
            ]
            total_courses = len(selected_courses)

            await _append_event(
                session, run.id, StudyRunEventLevel.INFO,
                f"Found {total_courses} course(s) to process",
                {"available": len(courses), "selected": total_courses},
            )
            await session.commit()

            # ── Rate limiter ────────────────────────────────────────────
            rate_limiter = AsyncRateLimiter(call_interval=job_delay)

            # ── Process each course sequentially ────────────────────────
            for course in selected_courses:
                # Cancellation check between courses
                if await _is_run_cancelled(session_factory, run.id):
                    run.status = StudyRunStatus.CANCELLED
                    run.finished_at = datetime.now(timezone.utc)
                    await _append_event(
                        session, run.id, StudyRunEventLevel.WARNING,
                        "Run cancelled by user",
                    )
                    await session.commit()
                    await _send_notification(
                        session, run.user_id,
                        "学习任务已取消 / Study Run Cancelled",
                        f"任务 #{run.id} 已被取消",
                    )
                    return {"run_id": run.id, "status": "cancelled"}

                course_name = course.get("title", course.get("courseName", "Unknown"))
                course_context = {
                    **course,
                    "account_id": str(account.id),
                    "course_id": course.get("course_id") or course.get("courseId"),
                    "clazz_id": course.get("clazz_id") or course.get("clazzId"),
                }

                await _append_event(
                    session, run.id, StudyRunEventLevel.INFO,
                    f"Processing course: {course_name}",
                )
                await session.commit()

                try:
                    points = await orchestrator.get_course_points(
                        str(account.id), course_context
                    )
                except Exception as exc:
                    await _append_event(
                        session, run.id, StudyRunEventLevel.ERROR,
                        f"Failed to fetch chapters for {course_name}: {exc}",
                    )
                    await session.commit()
                    processed_courses += 1
                    continue

                # ── Iterate chapters sequentially ───────────────────────
                max_chapter_retries = 3
                for point in points:
                    if point.get("has_finished"):
                        continue

                    # Cancellation check between chapters
                    if await _is_run_cancelled(session_factory, run.id):
                        run.status = StudyRunStatus.CANCELLED
                        run.finished_at = datetime.now(timezone.utc)
                        await _append_event(
                            session, run.id, StudyRunEventLevel.WARNING,
                            "Run cancelled by user",
                        )
                        await session.commit()
                        return {"run_id": run.id, "status": "cancelled"}

                    chapter_title = point.get("title", "Unknown chapter")
                    retries = 0
                    chapter_done = False

                    while retries <= max_chapter_retries and not chapter_done:
                        try:
                            await rate_limiter.limit_rate(random_time=True, random_max=0.3)
                            jobs, job_info = await orchestrator.get_course_jobs(
                                str(account.id), course_context, point
                            )
                        except Exception as exc:
                            await _append_event(
                                session, run.id, StudyRunEventLevel.WARNING,
                                f"Failed to fetch jobs for chapter '{chapter_title}': {exc}",
                            )
                            await session.commit()
                            retries += 1
                            if retries <= max_chapter_retries:
                                await asyncio.sleep(2.0 * retries)
                            continue

                        # Handle notOpen chapters (legacy pattern)
                        if job_info.get("notOpen", False):
                            retries += 1
                            if retries <= max_chapter_retries:
                                await _append_event(
                                    session, run.id, StudyRunEventLevel.WARNING,
                                    f"Chapter '{chapter_title}' not open yet, "
                                    f"retrying ({retries}/{max_chapter_retries})",
                                )
                                await session.commit()
                                await asyncio.sleep(3.0 * retries)
                                continue
                            # Exhausted retries — skip
                            await _append_event(
                                session, run.id, StudyRunEventLevel.WARNING,
                                f"Chapter '{chapter_title}' still not open after "
                                f"{max_chapter_retries} retries, skipping",
                            )
                            await session.commit()
                            break

                        # ── Process jobs within chapter sequentially ────
                        for job in jobs:
                            await rate_limiter.limit_rate(random_time=True, random_max=0.2)

                            try:
                                result = await orchestrator.process_job(
                                    course_context, job, job_info, speed=speed,
                                )
                            except Exception:
                                result = StudyResult.FAILED

                            processed_jobs += 1
                            if result == StudyResult.SUCCESS or result == StudyResult.SUCCESS.value:
                                successful_jobs += 1
                            elif result == StudyResult.SKIPPED or result == StudyResult.SKIPPED.value:
                                skipped_jobs += 1
                            else:
                                failed_jobs += 1

                        chapter_done = True

                    # Update progress after each chapter
                    await _update_progress(
                        session, run,
                        total_courses=total_courses,
                        processed_courses=processed_courses,
                        processed_jobs=processed_jobs,
                        successful_jobs=successful_jobs,
                        failed_jobs=failed_jobs,
                        skipped_jobs=skipped_jobs,
                    )

                processed_courses += 1
                await _append_event(
                    session, run.id, StudyRunEventLevel.INFO,
                    f"Finished course: {course_name}",
                    {"processed_jobs": processed_jobs, "successful": successful_jobs},
                )
                await _update_progress(
                    session, run,
                    total_courses=total_courses,
                    processed_courses=processed_courses,
                    processed_jobs=processed_jobs,
                    successful_jobs=successful_jobs,
                    failed_jobs=failed_jobs,
                    skipped_jobs=skipped_jobs,
                )

            # ── Finalize ────────────────────────────────────────────────
            # Re-check status (might have been cancelled between last commit and here)
            await session.refresh(run)
            if run.status == StudyRunStatus.CANCELLED:
                return {"run_id": run.id, "status": "cancelled"}

            run.status = StudyRunStatus.SUCCEEDED
            run.finished_at = datetime.now(timezone.utc)
            account.is_login_valid = True
            account.last_synced_at = datetime.now(timezone.utc)
            await _append_event(
                session, run.id, StudyRunEventLevel.INFO,
                "Study run completed",
                {
                    "courses": processed_courses,
                    "jobs": processed_jobs,
                    "ok": successful_jobs,
                    "fail": failed_jobs,
                    "skip": skipped_jobs,
                },
            )
            await session.commit()

            await _send_notification(
                session, run.user_id,
                "学习任务完成 / Study Run Completed",
                f"任务 #{run.id} 已完成\n"
                f"课程: {processed_courses}, "
                f"任务点: {processed_jobs} "
                f"(成功 {successful_jobs}, 失败 {failed_jobs}, 跳过 {skipped_jobs})",
            )

            return {
                "run_id": run.id,
                "status": "succeeded",
                "processed_courses": processed_courses,
                "processed_jobs": processed_jobs,
                "successful_jobs": successful_jobs,
                "failed_jobs": failed_jobs,
                "skipped_jobs": skipped_jobs,
            }

    except SoftTimeLimitExceeded:
        # Celery soft time limit — mark as failed and clean up
        async with session_factory() as session:
            run = await session.get(StudyRun, run_id)
            if run and run.status == StudyRunStatus.RUNNING:
                run.status = StudyRunStatus.FAILED
                run.finished_at = datetime.now(timezone.utc)
                await _append_event(
                    session, run.id, StudyRunEventLevel.ERROR,
                    "Study run timed out (soft time limit exceeded)",
                )
                await session.commit()
                await _send_notification(
                    session, run.user_id,
                    "学习任务超时 / Study Run Timed Out",
                    f"任务 #{run.id} 超时，已自动停止",
                )
        return {"run_id": run_id, "status": "failed", "message": "time limit exceeded"}

    except Exception as exc:
        # Unexpected error — mark run as failed
        try:
            async with session_factory() as session:
                run = await session.get(StudyRun, run_id)
                if run and run.status == StudyRunStatus.RUNNING:
                    run.status = StudyRunStatus.FAILED
                    run.finished_at = datetime.now(timezone.utc)
                    await _append_event(
                        session, run.id, StudyRunEventLevel.ERROR,
                        f"Unexpected error: {exc}",
                    )
                    await session.commit()
                    await _send_notification(
                        session, run.user_id,
                        "学习任务失败 / Study Run Failed",
                        f"任务 #{run.id} 出现错误: {exc}",
                    )
        except Exception:
            pass
        return {"run_id": run_id, "status": "failed", "message": str(exc)}

    finally:
        await session_service.close_all()


# ---------------------------------------------------------------------------
# Celery task definitions
# ---------------------------------------------------------------------------


@celery_app.task(name="chaoxing.tasks.process_study_run", bind=True, max_retries=2)
def process_study_run(self, run_id: int) -> dict[str, Any]:
    """Main Celery task: executes a full study run."""
    try:
        return run_async(process_study_run_job(run_id))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30) from exc


@celery_app.task(name="chaoxing.tasks.sync_courses")
def sync_courses(account_id: int) -> dict[str, Any]:
    return {"account_id": account_id, "status": "queued"}
