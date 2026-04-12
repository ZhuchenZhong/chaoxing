from unittest.mock import AsyncMock, Mock, patch

import pytest

from chaoxing.core.chaoxing.constants import StudyResult
from chaoxing.core.services.book_service import BookService
from chaoxing.core.services.document_service import DocumentService
from chaoxing.core.services.embedded_media_service import EmbeddedMediaService
from chaoxing.core.services.emptypage_service import EmptyPageService
from chaoxing.core.services.image_service import ImageService
from chaoxing.core.services.quiz_service import QuizService
from chaoxing.core.services.reading_service import ReadingService
from chaoxing.core.services.video_service import VideoService


@pytest.mark.asyncio
async def test_document_service_process() -> None:
    session_service = Mock()
    session_service.session_manager = Mock()
    service = DocumentService(session_service)

    with patch("chaoxing.core.services.document_service.ChaoxingClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client.mark_document_complete.return_value = True

        result = await service.process(
            {"course_id": "123", "account_id": "acc1"},
            {"type": "document", "jobid": "456"},
            {"dtoken": "token123"},
        )

    assert result == StudyResult.SUCCESS


@pytest.mark.asyncio
async def test_reading_service_process() -> None:
    session_service = Mock()
    session_service.session_manager = Mock()
    service = ReadingService(session_service)

    with patch("chaoxing.core.services.reading_service.ChaoxingClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client.mark_reading_complete.return_value = True

        result = await service.process(
            {"course_id": "123", "account_id": "acc1"},
            {"type": "read", "jobid": "456"},
            {"knowledgeid": "know789"},
        )

    assert result == StudyResult.SUCCESS


@pytest.mark.asyncio
async def test_emptypage_service_process() -> None:
    session_service = Mock()
    session_service.session_manager = Mock()
    service = EmptyPageService(session_service)

    with patch("chaoxing.core.services.emptypage_service.ChaoxingClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client.mark_emptypage_complete.return_value = True

        result = await service.process(
            {"course_id": "123", "account_id": "acc1"},
            {"type": "emptypage", "jobid": "456"},
            {},
        )

    assert result == StudyResult.SUCCESS


@pytest.mark.asyncio
async def test_image_service_process_insertimage() -> None:
    session_service = Mock()
    session_service.session_manager = Mock()
    service = ImageService(session_service)

    with patch("chaoxing.core.services.image_service.ChaoxingClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client.mark_page_viewed.return_value = True

        result = await service.process(
            {"course_id": "123", "account_id": "acc1"},
            {"type": "insertimage", "jobid": "456"},
            {"knowledgeid": "know789"},
        )

    assert result == StudyResult.SUCCESS


@pytest.mark.asyncio
async def test_book_service_process_insertbook() -> None:
    session_service = Mock()
    session_service.session_manager = Mock()
    service = BookService(session_service)

    with patch("chaoxing.core.services.book_service.ChaoxingClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client.mark_book_viewed.return_value = True

        result = await service.process(
            {"course_id": "123", "account_id": "acc1"},
            {"type": "insertbook", "jobid": "456"},
            {"bookid": "book789"},
        )

    assert result == StudyResult.SUCCESS


@pytest.mark.asyncio
async def test_embedded_media_service_process_insertvideo() -> None:
    session_service = Mock()
    session_service.session_manager = Mock()
    service = EmbeddedMediaService(session_service)

    with patch(
        "chaoxing.core.services.embedded_media_service.ChaoxingClient"
    ) as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client.mark_embedded_media_viewed.return_value = True

        result = await service.process(
            {"course_id": "123", "clazz_id": "456", "account_id": "acc1"},
            {"type": "insertvideo", "jobid": "789"},
            {"mediaid": "media-1"},
        )

    assert result == StudyResult.SUCCESS


@pytest.mark.asyncio
async def test_video_service_process_returns_success_when_already_complete() -> None:
    session_service = Mock()
    session_service.session_manager = Mock()
    service = VideoService(session_service)

    with patch("chaoxing.core.services.video_service.ChaoxingClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client.refresh_video_status.return_value = {
            "status": "success",
            "dtoken": "dt-1",
            "duration": 300,
        }
        mock_client.get_userid.return_value = "42"
        # First log_video_progress call returns passed=True
        mock_client.log_video_progress.return_value = (True, 200)

        result = await service.process(
            {"course_id": "123", "account_id": "acc1"},
            {"type": "video", "jobid": "456", "objectid": "obj-1"},
            {"dtoken": "token-1"},
            speed=2.0,
        )

    assert result == StudyResult.SUCCESS


@pytest.mark.asyncio
async def test_video_service_process_logs_progress_until_completion() -> None:
    session_service = Mock()
    session_service.session_manager = Mock()
    service = VideoService(session_service)

    with patch("chaoxing.core.services.video_service.ChaoxingClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client.refresh_video_status.return_value = {
            "status": "success",
            "dtoken": "dt-1",
            "duration": 120,
        }
        mock_client.get_userid.return_value = "42"
        # First call: not passed, second call: passed
        mock_client.log_video_progress.side_effect = [
            (False, 200),
            (True, 200),
        ]

        result = await service.process(
            {"course_id": "123", "account_id": "acc1"},
            {"type": "video", "jobid": "456", "objectid": "obj-1"},
            {"dtoken": "token-1"},
            speed=2.0,
        )

    assert result == StudyResult.SUCCESS
    assert mock_client.log_video_progress.called


@pytest.mark.asyncio
async def test_video_service_returns_failed_when_required_video_fields_are_missing() -> None:
    session_service = Mock()
    session_service.session_manager = Mock()
    service = VideoService(session_service)

    with patch("chaoxing.core.services.video_service.ChaoxingClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        # refresh_video_status returns None when objectid is missing/empty
        mock_client.refresh_video_status.return_value = None

        result = await service.process(
            {"course_id": "123", "account_id": "acc1"},
            {"type": "video", "jobid": "456"},
            {"duration": 120},
        )

    assert result == StudyResult.FAILED


@pytest.mark.asyncio
async def test_quiz_service_processes_work_task() -> None:
    session_service = Mock()
    session_service.session_manager = Mock()
    tiku_service = Mock()
    tiku_service.cover_rate = 0.8
    tiku_service.auto_submit = True

    # tiku_service.query() is now async and returns a TikuResult
    from chaoxing.core.tiku.base import TikuResult

    tiku_service.query = AsyncMock(
        return_value=TikuResult(answer="A", provider_name="test", from_cache=False)
    )
    tiku_service.judgement_select = Mock(return_value=True)
    service = QuizService(session_service, tiku_service)

    with patch("chaoxing.core.services.quiz_service.ChaoxingClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client.get_quiz_questions.return_value = [
            {"type": "0", "title": "Test question", "options": ["A", "B", "C"]}
        ]
        mock_client.submit_quiz_answers.return_value = True

        result = await service.process(
            {"course_id": "123", "account_id": "acc1"},
            {"type": "workid", "jobid": "456"},
            {"workid": "789"},
        )

    assert result == StudyResult.SUCCESS


@pytest.mark.asyncio
async def test_quiz_service_returns_failed_when_work_id_is_missing() -> None:
    session_service = Mock()
    service = QuizService(session_service)

    result = await service.process(
        {"course_id": "123", "account_id": "acc1"},
        {"type": "workid", "jobid": "456"},
        {},
    )

    assert result == StudyResult.FAILED


def test_quiz_service_matches_answer_to_options() -> None:
    service = QuizService(Mock())

    assert service._match_single_choice("B", ["Option A", "Option B"]) == "B"
    assert service._match_single_choice("Option B", ["Option A", "Option B"]) == "B"
    assert service._match_single_choice("Missing", ["Option A", "Option B"]) is None
