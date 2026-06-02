# -*- coding: utf-8 -*-
from __future__ import annotations

from threading import Lock

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskID, TextColumn, TimeElapsedColumn

from api.events import StudyEvent


class RichStudyDisplay:
    def __init__(self, console: Console | None = None):
        self.console = console or Console()
        self.progress: Progress | None = None
        self.tasks: dict[str, TaskID] = {}
        self.task_totals: dict[str, float] = {}
        self.lock = Lock()

    def __enter__(self):
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed:.0f}/{task.total:.0f}"),
            TimeElapsedColumn(),
            console=self.console,
            transient=False,
        )
        self.progress.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.progress:
            self.progress.__exit__(exc_type, exc, tb)

    def __call__(self, event: StudyEvent) -> None:
        with self.lock:
            self._handle(event)

    def _handle(self, event: StudyEvent) -> None:
        if not self.progress:
            return

        if event.kind == "job_done":
            key = event.key or event.job_id or event.title
            if key in self.tasks:
                self.progress.update(self.tasks[key], completed=self.task_totals.get(key, 1.0))
            message = event.message or f"任务完成: {event.title}"
            self.console.print(message)
            return

        if event.kind in {"course_start", "chapter_start", "chapter_done", "summary"}:
            message = event.message or event.title
            if message:
                self.console.print(message)
            return

        if event.kind == "job_start":
            key = event.key or event.job_id or event.title
            if key not in self.tasks:
                self.task_totals[key] = float(event.total or 1)
                self.tasks[key] = self.progress.add_task(
                    event.title or key,
                    total=self.task_totals[key],
                    completed=float(event.completed or 0),
                )
            return

        if event.kind == "job_progress":
            key = event.key or event.job_id or event.title
            self.task_totals[key] = float(event.total or 1)
            if key not in self.tasks:
                self.tasks[key] = self.progress.add_task(
                    event.title or key,
                    total=self.task_totals[key],
                    completed=float(event.completed or 0),
                )
            self.progress.update(
                self.tasks[key],
                total=self.task_totals[key],
                completed=float(event.completed or 0),
            )
