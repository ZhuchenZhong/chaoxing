import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from chaoxing.core.chaoxing.constants import StudyResult
from chaoxing.core.services.task_orchestrator import TaskOrchestrator


@pytest.mark.asyncio
async def test_orchestrator_routes_video_task():
    session_service = Mock()
    orchestrator = TaskOrchestrator(session_service)
    orchestrator.video_service.process = AsyncMock(return_value=StudyResult.SUCCESS)

    result = await orchestrator.process_job(
        {"course_id": "123"},
        {"type": "video", "jobid": "456"},
        {"dtoken": "token123"},
        speed=1.0,
    )

    assert result == StudyResult.SUCCESS
    orchestrator.video_service.process.assert_called_once()


def test_orchestrator_handles_unknown_task_type():
    session_service = Mock()
    orchestrator = TaskOrchestrator(session_service)

    result = asyncio.run(orchestrator.process_job({}, {"type": "unknown_type"}, {}))

    # Unknown job types are skipped gracefully rather than treated as failures
    assert result == StudyResult.SKIPPED


@pytest.mark.asyncio
async def test_orchestrator_login_account():
    session_service = Mock()
    orchestrator = TaskOrchestrator(session_service)
    orchestrator.auth_service.login = AsyncMock(return_value={"status": "success"})

    account = {"username": "test", "password": "pass"}
    result = await orchestrator.login_account("acc1", account)

    assert result["status"] == "success"
    orchestrator.auth_service.login.assert_called_once_with("acc1", account, False)


@pytest.mark.asyncio
async def test_orchestrator_get_courses():
    session_service = Mock()
    orchestrator = TaskOrchestrator(session_service)
    orchestrator.course_service.get_course_list = AsyncMock(return_value=[{"id": "1"}])

    courses = await orchestrator.get_account_courses("acc1")

    assert len(courses) == 1
    orchestrator.course_service.get_course_list.assert_called_once_with("acc1")
