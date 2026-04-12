from celery import Celery

from ..config import settings


celery_app = Celery(
    "chaoxing",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Execution
    task_track_started=True,
    task_time_limit=60 * 60,  # hard limit: 1 hour
    task_soft_time_limit=55 * 60,  # soft limit: 55 minutes
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
    worker_concurrency=4,
    # Queues & routing
    task_default_queue="default",
    task_routes={
        "chaoxing.tasks.process_study_run": {"queue": "study"},
        "chaoxing.tasks.sync_courses": {"queue": "default"},
    },
    # Result backend
    result_expires=3600,
)

celery_app.autodiscover_tasks(["chaoxing.tasks"])
