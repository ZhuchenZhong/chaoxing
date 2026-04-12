from unittest.mock import AsyncMock, Mock, patch

import pytest

from chaoxing.core.services.course_service import CourseService


@pytest.mark.asyncio
async def test_course_service_get_course_list():
    session_service = Mock()
    session_service.session_manager = Mock()

    course_service = CourseService(session_service)

    with patch("chaoxing.core.services.course_service.ChaoxingClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client.get_courses.return_value = [{"course_id": "123"}]

        courses = await course_service.get_course_list("account_1")

        assert isinstance(courses, list)
        assert courses[0]["course_id"] == "123"


@pytest.mark.asyncio
async def test_course_service_get_course_points():
    session_service = Mock()
    session_service.session_manager = Mock()

    course_service = CourseService(session_service)
    course = {"course_id": "123", "clazz_id": "456", "cpi": "789"}

    with patch("chaoxing.core.services.course_service.ChaoxingClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client.get_course_chapters.return_value = {"chapters": [{"id": "1"}]}

        points = await course_service.get_course_points("account_1", course)

        assert isinstance(points, list)
        assert points[0]["id"] == "1"


@pytest.mark.asyncio
async def test_course_service_get_course_jobs():
    session_service = Mock()
    session_service.session_manager = Mock()

    course_service = CourseService(session_service)
    course = {"courseId": "123", "clazzId": "456", "cpi": "789"}
    point = {"id": "point-1"}

    with patch("chaoxing.core.services.course_service.ChaoxingClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client.get_job_list.return_value = ([{"jobid": "job-1"}], {"knowledgeid": "point-1"})

        jobs, job_info = await course_service.get_course_jobs("account_1", course, point)

        assert jobs == [{"jobid": "job-1"}]
        assert job_info == {"knowledgeid": "point-1"}
