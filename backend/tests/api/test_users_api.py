from datetime import datetime, timezone
from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient

from chaoxing.db.database import get_db
from chaoxing.models.enums import NotOpenAction, UserRole
from chaoxing.models.study_profile import StudyProfile
from chaoxing.models.user import User


class FakeSession:
    def __init__(self):
        self.commits = 0
        self.refreshed = []
        self.added = []

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1

    async def refresh(self, obj):
        self.refreshed.append(obj)
        if getattr(obj, "updated_at", None) is None:
            obj.updated_at = datetime.now(timezone.utc)
        if getattr(obj, "created_at", None) is None:
            obj.created_at = datetime.now(timezone.utc)


def build_users_app(user: User, session: FakeSession) -> FastAPI:
    from chaoxing.api.users import router as users_router
    from chaoxing.auth.dependencies import get_current_active_user

    app = FastAPI()
    app.include_router(users_router, prefix="/users")

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


def build_profile(**overrides) -> StudyProfile:
    data = {
        "id": 5,
        "user_id": 3,
        "name": "default",
        "speed": Decimal("1.25"),
        "notopen_action": NotOpenAction.CONTINUE,
        "tiku_config": {"provider": "openai_compat"},
        "submit_config": {"submit": True},
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    data.update(overrides)
    return StudyProfile(**data)


def test_get_profile_returns_current_user():
    user = build_user()
    session = FakeSession()
    app = build_users_app(user, session)

    with TestClient(app) as client:
        response = client.get("/users/profile")

    assert response.status_code == 200
    assert response.json()["username"] == "tester"


def test_put_profile_updates_current_user():
    user = build_user()
    session = FakeSession()
    app = build_users_app(user, session)

    with TestClient(app) as client:
        response = client.put(
            "/users/profile",
            json={"display_name": "Updated", "email": "updated@example.com"},
        )

    assert response.status_code == 200
    assert response.json()["display_name"] == "Updated"
    assert user.email == "updated@example.com"
    assert session.commits == 1


def test_get_study_config_returns_default_profile(monkeypatch):
    user = build_user()
    session = FakeSession()
    app = build_users_app(user, session)

    async def fake_get_profile(*_args):
        return build_profile()

    monkeypatch.setattr("chaoxing.api.users.get_or_create_default_profile", fake_get_profile)

    with TestClient(app) as client:
        response = client.get("/users/study-config")

    assert response.status_code == 200
    assert response.json()["speed"] == 1.25
    assert response.json()["notopen_action"] == "continue"


def test_put_tiku_config_updates_profile(monkeypatch):
    user = build_user()
    session = FakeSession()
    app = build_users_app(user, session)
    profile = build_profile()

    async def fake_get_profile(*_args):
        return profile

    monkeypatch.setattr("chaoxing.api.users.get_or_create_default_profile", fake_get_profile)

    with TestClient(app) as client:
        response = client.put(
            "/users/tiku-config",
            json={"tiku_config": {"provider": "siliconflow", "model": "deepseek"}},
        )

    assert response.status_code == 200
    assert response.json()["tiku_config"]["provider"] == "siliconflow"
    assert profile.tiku_config["model"] == "deepseek"
    assert session.commits == 1
