from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from chaoxing.db.database import get_db
from chaoxing.models.chaoxing_account import ChaoxingAccount
from chaoxing.models.enums import ChaoxingAuthType, UserRole
from chaoxing.models.user import User


class FakeSession:
    async def commit(self):
        return None

    async def refresh(self, _obj):
        return None


def build_courses_app(user: User, session: FakeSession) -> FastAPI:
    from chaoxing.api.courses import router as courses_router
    from chaoxing.auth.dependencies import get_current_active_user

    app = FastAPI()
    app.include_router(courses_router, prefix="/accounts")

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


def build_account(**overrides) -> ChaoxingAccount:
    data = {
        "id": 21,
        "user_id": 3,
        "display_name": "Main Account",
        "auth_type": ChaoxingAuthType.PASSWORD,
        "username_encrypted": "encrypted-u",
        "password_encrypted": "encrypted-p",
        "cookies_encrypted": None,
        "is_login_valid": True,
        "last_synced_at": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    data.update(overrides)
    return ChaoxingAccount(**data)


def test_get_courses_returns_live_course_list(monkeypatch):
    app = build_courses_app(build_user(), FakeSession())
    account = build_account()

    async def fake_load_account(*_args):
        return account

    async def fake_get_courses(*_args):
        return [{"courseId": "1001", "clazzId": "2001", "cpi": "root-cpi", "title": "Course A"}]

    monkeypatch.setattr("chaoxing.api.courses.load_user_account", fake_load_account)
    monkeypatch.setattr("chaoxing.api.courses.get_account_courses", fake_get_courses)

    with TestClient(app) as client:
        response = client.get("/accounts/21/courses")

    assert response.status_code == 200
    assert response.json()[0]["courseId"] == "1001"


def test_get_course_chapters_returns_live_chapter_payload(monkeypatch):
    app = build_courses_app(build_user(), FakeSession())
    account = build_account()

    async def fake_load_account(*_args):
        return account

    async def fake_get_chapters(*_args):
        return {
            "courseId": "1001",
            "hasLocked": False,
            "points": [{"id": "123", "title": "第一章", "has_finished": True, "need_unlock": False}],
        }

    monkeypatch.setattr("chaoxing.api.courses.load_user_account", fake_load_account)
    monkeypatch.setattr("chaoxing.api.courses.get_account_chapters", fake_get_chapters)

    with TestClient(app) as client:
        response = client.get("/accounts/21/courses/1001/chapters")

    assert response.status_code == 200
    assert response.json()["courseId"] == "1001"
    assert response.json()["points"][0]["id"] == "123"
