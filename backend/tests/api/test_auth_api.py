from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from chaoxing.db.database import get_db
from chaoxing.models.enums import UserRole
from chaoxing.models.invite import Invite
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
            obj.id = 1
        now = datetime.now(timezone.utc)
        if getattr(obj, "created_at", None) is None:
            obj.created_at = now
        if getattr(obj, "updated_at", None) is None:
            obj.updated_at = now


def build_auth_app(session: FakeSession) -> FastAPI:
    from chaoxing.api.auth import router as auth_router
    from chaoxing.api.rate_limit import login_limiter, register_limiter

    app = FastAPI()
    app.include_router(auth_router, prefix="/auth")

    async def override_db():
        yield session

    async def noop_limiter():
        pass

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[login_limiter] = noop_limiter
    app.dependency_overrides[register_limiter] = noop_limiter
    return app


def build_user(**overrides) -> User:
    from chaoxing.auth.utils import get_password_hash

    data = {
        "id": 1,
        "email": "user@example.com",
        "username": "testuser",
        "display_name": "Test User",
        "password_hash": get_password_hash("password123"),
        "role": UserRole.USER,
        "is_active": True,
        "must_change_password": False,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    data.update(overrides)
    return User(**data)


def build_invite(**overrides) -> Invite:
    data = {
        "id": 7,
        "code": "INVITE-001",
        "created_by_user_id": 9,
        "max_uses": 3,
        "used_count": 0,
        "bonus_credits": 0,
        "is_active": True,
        "expires_at": None,
        "created_at": datetime.now(timezone.utc),
    }
    data.update(overrides)
    return Invite(**data)


def test_register_creates_user_with_valid_invite(monkeypatch):
    session = FakeSession()
    app = build_auth_app(session)

    async def fake_get_by_email(*_args):
        return None

    async def fake_get_by_username(*_args):
        return None

    async def fake_load_invite(*_args):
        return build_invite()

    monkeypatch.setattr("chaoxing.api.auth.User.get_by_email", fake_get_by_email)
    monkeypatch.setattr("chaoxing.api.auth.User.get_by_username", fake_get_by_username)
    monkeypatch.setattr("chaoxing.api.auth.load_invite_by_code", fake_load_invite)

    with TestClient(app) as client:
        response = client.post(
            "/auth/register",
            json={
                "email": "new@example.com",
                "username": "newuser",
                "display_name": "New User",
                "password": "password123",
                "invite_code": "INVITE-001",
            },
        )

    assert response.status_code == 201
    assert response.json()["username"] == "newuser"
    created_user = session.added[0]
    assert created_user.invite_code_id == 7
    assert created_user.invited_by_user_id == 9
    assert session.commits == 1


def test_login_returns_tokens_for_valid_credentials(monkeypatch):
    session = FakeSession()
    app = build_auth_app(session)

    async def fake_get_by_username(*_args):
        return build_user()

    monkeypatch.setattr("chaoxing.api.auth.User.get_by_username", fake_get_by_username)

    with TestClient(app) as client:
        response = client.post(
            "/auth/login",
            json={"username": "testuser", "password": "password123"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["access_token"]
    assert payload["refresh_token"]


def test_refresh_returns_new_tokens_for_valid_refresh_token(monkeypatch):
    from chaoxing.auth.utils import create_refresh_token

    session = FakeSession()
    app = build_auth_app(session)
    user = build_user()
    refresh_token = create_refresh_token({"sub": str(user.id), "role": user.role})

    async def fake_get(*_args):
        return user

    monkeypatch.setattr("chaoxing.api.auth.User.get", fake_get)

    with TestClient(app) as client:
        response = client.post("/auth/refresh", json={"refresh_token": refresh_token})

    assert response.status_code == 200
    payload = response.json()
    assert payload["access_token"]
    assert payload["refresh_token"]


def test_me_returns_current_user():
    from chaoxing.auth.dependencies import get_current_active_user

    session = FakeSession()
    app = build_auth_app(session)
    user = build_user()

    async def override_current_user():
        return user

    app.dependency_overrides[get_current_active_user] = override_current_user

    with TestClient(app) as client:
        response = client.get("/auth/me")

    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"


def test_change_password_updates_hash_and_clears_reset_flag():
    from chaoxing.auth.dependencies import get_current_active_user
    from chaoxing.auth.utils import verify_password

    session = FakeSession()
    app = build_auth_app(session)
    user = build_user(must_change_password=True)

    async def override_current_user():
        return user

    app.dependency_overrides[get_current_active_user] = override_current_user

    with TestClient(app) as client:
        response = client.post(
            "/auth/change-password",
            json={"current_password": "password123", "new_password": "new-password-456"},
        )

    assert response.status_code == 200
    assert verify_password("new-password-456", user.password_hash)
    assert user.must_change_password is False
    assert session.commits == 1
