"""Celery worker entry point.

Start the worker with:
    celery -A chaoxing.worker worker --loglevel=info -Q default,study
"""

from .tasks.celery_app import celery_app  # noqa: F401 — Celery discovers this

__all__ = ["celery_app"]
