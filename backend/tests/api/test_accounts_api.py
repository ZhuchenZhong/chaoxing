from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from chaoxing.db.database import get_db
from chaoxing.models.chaoxing_account import ChaoxingAccount
from chaoxing.models.enums import ChaoxingAuthType, UserRole
from chaoxing.models.user import User


class FakeSession:
    def __init__(self):
        self.added = []
        self.deleted = []
        self.commits = 0
        self.refreshed = []

    def add(self, obj):
        self.added.append(obj)

    async def delete(self, obj):
        self.deleted.append(obj)

    async def commit(self):
        self.commits += 1

    async def refresh(self, obj):
        self.refreshed.append(obj)
        if getattr(obj, "id", None) is None:
            obj.id = 11
        now = datetime.now(timezone.utc)
        if getattr(obj, "created_at", None) is None:
            obj.created_at = now
        if getattr(obj, "updated_at", None) is None:
            obj.updated_at = now


def build_accounts_app(user: User, session: FakeSession) -> FastAPI:
    from chaoxing.api.accounts import router as accounts_router
    from chaoxing.auth.dependencies import get_current_active_user

    app = FastAPI()
    app.include_router(accounts_router, prefix="/accounts")

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
        "is_login_valid": False,
        "last_synced_at": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    data.update(overrides)
    return ChaoxingAccount(**data)


def test_create_account_persists_password_credentials():
    session = FakeSession()
    app = build_accounts_app(build_user(), session)

    with TestClient(app) as client:
        response = client.post(
            "/accounts",
            json={
                "display_name": "Phone Login",
                "auth_type": "password",
                "username": "13800138000",
                "password": "secret123",
            },
        )

    assert response.status_code == 201
    created = session.added[0]
    assert created.display_name == "Phone Login"
    assert created.auth_type == ChaoxingAuthType.PASSWORD
    assert created.username_encrypted
    assert created.password_encrypted
    assert session.commits == 1


def test_list_accounts_returns_current_user_accounts(monkeypatch):
    session = FakeSession()
    app = build_accounts_app(build_user(), session)

    async def fake_load_accounts(*_args):
        return [build_account()]

    monkeypatch.setattr("chaoxing.api.accounts.load_user_accounts", fake_load_accounts)

    with TestClient(app) as client:
        response = client.get("/accounts")

    assert response.status_code == 200
    assert response.json()[0]["display_name"] == "Main Account"


def test_delete_account_removes_owned_account(monkeypatch):
    session = FakeSession()
    app = build_accounts_app(build_user(), session)
    account = build_account()

    async def fake_load_account(*_args):
        return account

    monkeypatch.setattr("chaoxing.api.accounts.load_user_account", fake_load_account)

    with TestClient(app) as client:
        response = client.delete("/accounts/21")

    assert response.status_code == 200
    assert session.deleted == [account]
    assert session.commits == 1


def test_verify_account_updates_login_state(monkeypatch):
    session = FakeSession()
    app = build_accounts_app(build_user(), session)
    account = build_account()

    async def fake_load_account(*_args):
        return account

    async def fake_verify(*_args):
        return {"status": "success", "message": "登录成功", "is_login_valid": True}

    monkeypatch.setattr("chaoxing.api.accounts.load_user_account", fake_load_account)
    monkeypatch.setattr("chaoxing.api.accounts.verify_account_session", fake_verify)

    with TestClient(app) as client:
        response = client.post("/accounts/21/verify")

    assert response.status_code == 200
    assert response.json()["is_login_valid"] is True
    assert account.is_login_valid is True
    assert session.commits == 1


def test_sync_courses_returns_course_list(monkeypatch):
    session = FakeSession()
    app = build_accounts_app(build_user(), session)
    account = build_account(is_login_valid=True)

    async def fake_load_account(*_args):
        return account

    async def fake_sync(*_args):
        return [
            {"courseId": "1001", "title": "Course A"},
            {"courseId": "1002", "title": "Course B"},
        ]

    monkeypatch.setattr("chaoxing.api.accounts.load_user_account", fake_load_account)
    monkeypatch.setattr("chaoxing.api.accounts.sync_account_courses", fake_sync)

    with TestClient(app) as client:
        response = client.post("/accounts/21/sync-courses")

    assert response.status_code == 200
    assert response.json()["course_count"] == 2
    assert response.json()["courses"][0]["courseId"] == "1001"
