# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class StudyEvent:
    kind: str
    title: str = ""
    key: str = ""
    course_id: str = ""
    chapter_id: str = ""
    job_id: str = ""
    completed: int | float | None = None
    total: int | float | None = None
    status: str = ""
    message: str = ""
    extra: dict[str, Any] | None = None


EventSink = Callable[[StudyEvent], None]


def emit_event(event_sink: EventSink | None, event: StudyEvent) -> None:
    if event_sink is None:
        return
    try:
        event_sink(event)
    except Exception:
        # Progress rendering must never break study execution.
        return
