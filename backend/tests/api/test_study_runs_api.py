from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from chaoxing.db.database import get_db
from chaoxing.models.enums import UserRole
from chaoxing.models.study_run import StudyRun, StudyRunEvent, StudyRunEventLevel, StudyRunStatus
from chaoxing.models.user import User


class FakeSession:
    def __init__(self):
        self.added = []
        self.commits = 0
        self.refreshed = []

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1

    async def refresh(self, obj):
        self.refreshed.append(obj)
        if getattr(obj, "id", None) is None:
            obj.id = 31
        now = datetime.now(timezone.utc)
        if getattr(obj, "created_at", None) is None:
            obj.created_at = now
        if getattr(obj, "updated_at", None) is None:
            obj.updated_at = now


def build_runs_app(user: User, session: FakeSession) -> FastAPI:
    from chaoxing.api.study_runs import router as runs_router
    from chaoxing.auth.dependencies import get_current_active_user

    app = FastAPI()
    app.include_router(runs_router, prefix="/study-runs")

    async def override_db():
        yield session

    async def override_current_user():
        return user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_active_user] = override_current_user
    return app


def build_user(**overrides) -> User:
    data = {
        "id": 3,
        "email": "user@example.com",
        "username": "tester",
        "display_name": "Tester",
        "password_hash": "hashed-password",
        "role": UserRole.USER,
        "is_active": True,
        "must_change_password": False,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    data.update(overrides)
    return User(**data)


def build_run(**overrides) -> StudyRun:
    data = {
        "id": 31,
        "user_id": 3,
        "account_id": 21,
        "profile_id": None,
        "course_ids": ["1001"],
        "status": StudyRunStatus.QUEUED,
        "celery_task_id": "celery-1",
        "progress_json": {"processed_jobs": 0},
        "started_at": None,
        "finished_at": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    data.update(overrides)
    return StudyRun(**data)


def build_event(**overrides) -> StudyRunEvent:
    data = {
        "id": 9,
        "run_id": 31,
        "level": StudyRunEventLevel.INFO,
        "message": "Study run started",
        "detail_json": {"course_ids": ["1001"]},
        "created_at": datetime.now(timezone.utc),
    }
    data.update(overrides)
    return StudyRunEvent(**data)


def test_create_study_run_enqueues_background_job(monkeypatch):
    session = FakeSession()
    app = build_runs_app(build_user(), session)

    async def fake_load_account(*_args):
        return object()

    def fake_enqueue(run):
        return "celery-123"

    monkeypatch.setattr("chaoxing.api.study_runs.load_user_account", fake_load_account)
    monkeypatch.setattr("chaoxing.api.study_runs.enqueue_study_run", fake_enqueue)

    with TestClient(app) as client:
        response = client.post(
            "/study-runs",
            json={"account_id": 21, "course_ids": ["1001", "1002"], "profile_id": 7},
        )

    assert response.status_code == 201
    assert response.json()["status"] == "queued"
    assert response.json()["celery_task_id"] == "celery-123"
    created = session.added[0]
    assert created.account_id == 21
    assert created.course_ids == ["1001", "1002"]


def test_list_study_runs_returns_current_user_runs(monkeypatch):
    session = FakeSession()
    app = build_runs_app(build_user(), session)

    async def fake_load_runs(*_args):
        return [build_run()]

    monkeypatch.setattr("chaoxing.api.study_runs.load_user_runs", fake_load_runs)

    with TestClient(app) as client:
        response = client.get("/study-runs")

    assert response.status_code == 200
    assert response.json()[0]["id"] == 31


def test_get_study_run_returns_events(monkeypatch):
    session = FakeSession()
    app = build_runs_app(build_user(), session)
    run = build_run()
    event = build_event()

    async def fake_load_run(*_args):
        return run

    async def fake_load_events(*_args):
        return [event]

    monkeypatch.setattr("chaoxing.api.study_runs.load_user_run", fake_load_run)
    monkeypatch.setattr("chaoxing.api.study_runs.load_run_events", fake_load_events)

    with TestClient(app) as client:
        response = client.get("/study-runs/31")

    assert response.status_code == 200
    assert response.json()["id"] == 31
    assert response.json()["events"][0]["message"] == "Study run started"


def test_cancel_study_run_updates_status(monkeypatch):
    session = FakeSession()
    app = build_runs_app(build_user(), session)
    run = build_run(status=StudyRunStatus.RUNNING)

    async def fake_load_run(*_args):
        return run

    monkeypatch.setattr("chaoxing.api.study_runs.load_user_run", fake_load_run)

    with TestClient(app) as client:
        response = client.post("/study-runs/31/cancel")

    assert response.status_code == 200
    # When a RUNNING run is cancelled, status transitions to STOPPING first
    # (so the running task can finish its current step gracefully)
    assert response.json()["status"] == "stopping"
    assert run.status == StudyRunStatus.STOPPING
    assert session.commits == 1
