import pytest

from chaoxing.tasks.study_tasks import run_async


async def _sample_async_result() -> str:
    return "done"


def test_run_async_executes_coroutine_and_returns_result() -> None:
    assert run_async(_sample_async_result()) == "done"


async def _sample_async_error() -> None:
    raise ValueError("bridge failed")


class SampleAwaitable:
    def __await__(self):
        async def _inner() -> str:
            return "done"

        return _inner().__await__()


def test_run_async_propagates_coroutine_exceptions() -> None:
    with pytest.raises(ValueError, match="bridge failed"):
        run_async(_sample_async_error())


def test_run_async_rejects_non_coroutine_awaitables() -> None:
    with pytest.raises(TypeError, match=r"run_async\(\) requires a coroutine object"):
        run_async(SampleAwaitable())


@pytest.mark.anyio
async def test_run_async_rejects_calls_from_active_event_loop() -> None:
    with pytest.raises(
        RuntimeError,
        match=r"run_async\(\) cannot be called while an event loop is already running",
    ):
        run_async(_sample_async_result())
