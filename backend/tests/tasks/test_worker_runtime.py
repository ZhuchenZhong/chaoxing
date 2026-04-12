from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from chaoxing.core.chaoxing.crypto import AESCipher
from chaoxing.db.database import Base
from chaoxing.models.chaoxing_account import ChaoxingAccount
from chaoxing.models.enums import ChaoxingAuthType, UserRole
from chaoxing.models.study_run import StudyRun, StudyRunEvent, StudyRunStatus
from chaoxing.models.user import User
from chaoxing.tasks.study_tasks import process_study_run_job


@pytest.fixture
async def session_factory(tmp_path: Path):
    database_path = tmp_path / "worker-runtime.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}", future=True)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


async def _seed_run(session_factory: async_sessionmaker) -> int:
    cipher = AESCipher()
    async with session_factory() as session:
        user = User(
            email="user@example.com",
            username="tester",
            display_name="Tester",
            password_hash="hashed",
            role=UserRole.USER,
            is_active=True,
            must_change_password=False,
        )
        session.add(user)
        await session.flush()

        account = ChaoxingAccount(
            user_id=user.id,
            display_name="Main account",
            auth_type=ChaoxingAuthType.PASSWORD,
            username_encrypted=cipher.encrypt("alice"),
            password_encrypted=cipher.encrypt("secret"),
            is_login_valid=False,
        )
        session.add(account)
        await session.flush()

        run = StudyRun(
            user_id=user.id,
            account_id=account.id,
            profile_id=None,
            course_ids=["1001", "1002"],
            status=StudyRunStatus.QUEUED,
            progress_json={},
        )
        session.add(run)
        await session.commit()
        return run.id


@pytest.mark.asyncio
async def test_process_study_run_job_marks_run_succeeded_and_persists_events(session_factory) -> None:
    run_id = await _seed_run(session_factory)
    orchestrator = Mock()
    orchestrator.login_account = AsyncMock(return_value={"status": "success", "message": "登录成功"})
    orchestrator.get_account_courses = AsyncMock(
        return_value=[
            {"courseId": "1001", "title": "Course A"},
            {"courseId": "1002", "title": "Course B"},
            {"courseId": "9999", "title": "Other"},
        ]
    )
    orchestrator.get_course_points = AsyncMock(return_value=[])

    result = await process_study_run_job(
        run_id,
        session_factory=session_factory,
        orchestrator_factory=lambda: orchestrator,
    )

    assert result["status"] == "succeeded"
    assert result["processed_courses"] == 2

    async with session_factory() as session:
        run = await session.get(StudyRun, run_id)
        events = list(
            (
                await session.execute(
                    select(StudyRunEvent).where(StudyRunEvent.run_id == run_id).order_by(StudyRunEvent.id)
                )
            )
            .scalars()
            .all()
        )

    assert run is not None
    assert run.status == StudyRunStatus.SUCCEEDED
    assert run.started_at is not None
    assert run.finished_at is not None
    assert run.progress_json["total_courses"] == 2
    assert run.progress_json["processed_courses"] == 2
    assert run.progress_json["processed_jobs"] == 0
    assert run.progress_json["successful_jobs"] == 0
    assert run.progress_json["failed_jobs"] == 0
    assert len(events) >= 2
    assert events[0].message == "Study run started"
    assert events[-1].message == "Study run completed"


@pytest.mark.asyncio
async def test_process_study_run_job_marks_run_failed_when_login_fails(session_factory) -> None:
    run_id = await _seed_run(session_factory)
    orchestrator = Mock()
    orchestrator.login_account = AsyncMock(return_value={"status": "error", "message": "bad login"})
    orchestrator.get_account_courses = AsyncMock()

    result = await process_study_run_job(
        run_id,
        session_factory=session_factory,
        orchestrator_factory=lambda: orchestrator,
    )

    assert result["status"] == "failed"
    assert result["message"] == "bad login"

    async with session_factory() as session:
        run = await session.get(StudyRun, run_id)
        events = list(
            (
                await session.execute(
                    select(StudyRunEvent).where(StudyRunEvent.run_id == run_id).order_by(StudyRunEvent.id)
                )
            )
            .scalars()
            .all()
        )

    assert run is not None
    assert run.status == StudyRunStatus.FAILED
    assert run.finished_at is not None
    assert len(events) == 2
    assert events[1].message == "Login failed"
    assert events[1].detail_json == {"reason": "bad login"}


@pytest.mark.asyncio
async def test_process_study_run_job_executes_course_points_and_jobs(session_factory) -> None:
    run_id = await _seed_run(session_factory)
    orchestrator = Mock()
    orchestrator.login_account = AsyncMock(return_value={"status": "success", "message": "登录成功"})
    orchestrator.get_account_courses = AsyncMock(
        return_value=[{"courseId": "1001", "clazzId": "2001", "cpi": "cpi-1", "title": "Course A"}]
    )
    orchestrator.get_course_points = AsyncMock(
        return_value=[{"id": "point-1", "title": "Chapter 1", "has_finished": False}]
    )
    orchestrator.get_course_jobs = AsyncMock(
        return_value=([{"type": "document", "jobid": "job-1"}], {"knowledgeid": "point-1"})
    )
    orchestrator.process_job = AsyncMock(return_value="success")

    result = await process_study_run_job(
        run_id,
        session_factory=session_factory,
        orchestrator_factory=lambda: orchestrator,
    )

    assert result["status"] == "succeeded"
    assert result["processed_jobs"] == 1
    orchestrator.get_course_points.assert_awaited_once()
    orchestrator.get_course_jobs.assert_awaited_once()
    orchestrator.process_job.assert_awaited_once()

    async with session_factory() as session:
        run = await session.get(StudyRun, run_id)

    assert run is not None
    assert run.progress_json["processed_jobs"] == 1
    assert run.progress_json["successful_jobs"] == 1
