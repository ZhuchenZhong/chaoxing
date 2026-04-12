from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from chaoxing.db.database import get_db
from chaoxing.models.billing import RechargeOrder, RechargeOrderStatus
from chaoxing.models.enums import UserRole
from chaoxing.models.invite import Invite
from chaoxing.models.study_run import StudyRun, StudyRunStatus
from chaoxing.models.system_setting import SystemSetting
from chaoxing.models.tiku_provider import TikuProvider, TikuProviderType
from chaoxing.models.user import User
from chaoxing.models.wallet import Wallet


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
            obj.id = 77
        now = datetime.now(timezone.utc)
        if getattr(obj, "created_at", None) is None:
            obj.created_at = now
        if getattr(obj, "updated_at", None) is None:
            obj.updated_at = now


def build_admin_app(user: User, session: FakeSession) -> FastAPI:
    from chaoxing.api.admin import router as admin_router
    from chaoxing.auth.dependencies import get_current_active_user

    app = FastAPI()
    app.include_router(admin_router, prefix="/admin")

    async def override_db():
        yield session

    async def override_current_user():
        return user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_active_user] = override_current_user
    return app


def build_user(**overrides) -> User:
    data = {
        "id": 1,
        "email": "admin@example.com",
        "username": "admin",
        "display_name": "Admin",
        "password_hash": "hashed-password",
        "role": UserRole.ADMIN,
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
        "status": StudyRunStatus.RUNNING,
        "celery_task_id": "celery-1",
        "progress_json": {"processed_jobs": 1},
        "started_at": datetime.now(timezone.utc),
        "finished_at": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    data.update(overrides)
    return StudyRun(**data)


def build_order(**overrides) -> RechargeOrder:
    data = {
        "id": 9,
        "user_id": 3,
        "package_id": None,
        "amount_cents": 1999,
        "requested_credits": 200,
        "payment_channel": "alipay",
        "payment_reference": "trade-001",
        "proof_path": None,
        "status": RechargeOrderStatus.PENDING,
        "reviewed_by_user_id": None,
        "reviewed_at": None,
        "review_note": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    data.update(overrides)
    return RechargeOrder(**data)


def build_invite(**overrides) -> Invite:
    data = {
        "id": 5,
        "code": "INV-001",
        "created_by_user_id": 1,
        "max_uses": 3,
        "used_count": 0,
        "bonus_credits": 10,
        "is_active": True,
        "expires_at": None,
        "created_at": datetime.now(timezone.utc),
    }
    data.update(overrides)
    return Invite(**data)


def build_wallet(**overrides) -> Wallet:
    data = {
        "id": 12,
        "user_id": 3,
        "balance": 100,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    data.update(overrides)
    return Wallet(**data)


def build_provider(**overrides) -> TikuProvider:
    data = {
        "id": 15,
        "user_id": None,
        "name": "Main Provider",
        "provider_type": TikuProviderType.OPENAI_COMPAT,
        "config_encrypted": {"api_key": "secret"},
        "priority": 10,
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    data.update(overrides)
    return TikuProvider(**data)


def build_setting(**overrides) -> SystemSetting:
    data = {
        "key": "platform",
        "value": {"invite_only": True},
        "updated_at": datetime.now(timezone.utc),
    }
    data.update(overrides)
    return SystemSetting(**data)


def test_get_admin_users_returns_entries(monkeypatch):
    app = build_admin_app(build_user(), FakeSession())

    async def fake_load_users(*_args):
        return [build_user(id=3, username="tester", role=UserRole.USER)]

    monkeypatch.setattr("chaoxing.api.admin.load_users", fake_load_users)

    with TestClient(app) as client:
        response = client.get("/admin/users")

    assert response.status_code == 200
    assert response.json()[0]["username"] == "tester"


def test_put_admin_user_updates_fields(monkeypatch):
    session = FakeSession()
    app = build_admin_app(build_user(), session)
    target = build_user(id=3, username="tester", role=UserRole.USER)

    async def fake_load_user(*_args):
        return target

    monkeypatch.setattr("chaoxing.api.admin.load_user_by_id", fake_load_user)

    with TestClient(app) as client:
        response = client.put(
            "/admin/users/3",
            json={"display_name": "Updated", "role": "admin", "is_active": False},
        )

    assert response.status_code == 200
    assert response.json()["display_name"] == "Updated"
    assert target.role == UserRole.ADMIN
    assert target.is_active is False
    assert session.commits == 1


def test_get_admin_tasks_returns_runs(monkeypatch):
    app = build_admin_app(build_user(), FakeSession())

    async def fake_load_runs(*_args):
        return [build_run()]

    monkeypatch.setattr("chaoxing.api.admin.load_study_runs", fake_load_runs)

    with TestClient(app) as client:
        response = client.get("/admin/tasks")

    assert response.status_code == 200
    assert response.json()[0]["id"] == 31


def test_get_admin_recharge_orders_returns_entries(monkeypatch):
    app = build_admin_app(build_user(), FakeSession())

    async def fake_load_orders(*_args):
        return [build_order()]

    monkeypatch.setattr("chaoxing.api.admin.load_recharge_orders", fake_load_orders)

    with TestClient(app) as client:
        response = client.get("/admin/recharge-orders")

    assert response.status_code == 200
    assert response.json()[0]["status"] == RechargeOrderStatus.PENDING.value


def test_put_admin_recharge_order_approves_and_credits_wallet(monkeypatch):
    session = FakeSession()
    admin = build_user()
    app = build_admin_app(admin, session)
    order = build_order()
    wallet = build_wallet()

    async def fake_load_order(*_args):
        return order

    async def fake_get_wallet(*_args):
        return wallet

    monkeypatch.setattr("chaoxing.api.admin.load_recharge_order", fake_load_order)
    monkeypatch.setattr("chaoxing.api.admin.get_or_create_user_wallet", fake_get_wallet)

    with TestClient(app) as client:
        response = client.put(
            "/admin/recharge-orders/9",
            json={"status": "approved", "review_note": "checked"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == RechargeOrderStatus.APPROVED.value
    assert order.reviewed_by_user_id == admin.id
    assert wallet.balance == 300
    assert session.added[-1].delta == 200
    assert session.commits == 1


def test_get_admin_invites_returns_entries(monkeypatch):
    app = build_admin_app(build_user(), FakeSession())

    async def fake_load_invites(*_args):
        return [build_invite()]

    monkeypatch.setattr("chaoxing.api.admin.load_invites", fake_load_invites)

    with TestClient(app) as client:
        response = client.get("/admin/invites")

    assert response.status_code == 200
    assert response.json()[0]["code"] == "INV-001"


def test_post_admin_invites_creates_entry():
    session = FakeSession()
    app = build_admin_app(build_user(), session)

    with TestClient(app) as client:
        response = client.post(
            "/admin/invites",
            json={"code": "INV-NEW", "max_uses": 5, "bonus_credits": 20},
        )

    assert response.status_code == 201
    assert response.json()["code"] == "INV-NEW"
    created = session.added[0]
    assert created.created_by_user_id == 1
    assert created.max_uses == 5
    assert session.commits == 1


def test_delete_admin_invite_marks_inactive(monkeypatch):
    session = FakeSession()
    app = build_admin_app(build_user(), session)
    invite = build_invite()

    async def fake_load_invite(*_args):
        return invite

    monkeypatch.setattr("chaoxing.api.admin.load_invite", fake_load_invite)

    with TestClient(app) as client:
        response = client.delete("/admin/invites/5")

    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert invite.is_active is False
    assert session.commits == 1


def test_get_admin_tiku_providers_returns_entries(monkeypatch):
    app = build_admin_app(build_user(), FakeSession())

    async def fake_load_providers(*_args):
        return [build_provider()]

    monkeypatch.setattr("chaoxing.api.admin.load_tiku_providers", fake_load_providers)

    with TestClient(app) as client:
        response = client.get("/admin/tiku-providers")

    assert response.status_code == 200
    assert response.json()[0]["provider_type"] == TikuProviderType.OPENAI_COMPAT.value


def test_post_admin_tiku_provider_creates_entry():
    session = FakeSession()
    app = build_admin_app(build_user(), session)

    with TestClient(app) as client:
        response = client.post(
            "/admin/tiku-providers",
            json={
                "name": "Backup Provider",
                "provider_type": "siliconflow",
                "config": {"api_key": "secret"},
                "priority": 50,
                "is_active": True,
            },
        )

    assert response.status_code == 201
    assert response.json()["name"] == "Backup Provider"
    created = session.added[0]
    assert created.provider_type == TikuProviderType.SILICONFLOW
    assert created.config_encrypted["api_key"] == "secret"
    assert session.commits == 1


def test_get_admin_settings_returns_entries(monkeypatch):
    app = build_admin_app(build_user(), FakeSession())

    async def fake_load_settings(*_args):
        return [build_setting()]

    monkeypatch.setattr("chaoxing.api.admin.load_system_settings", fake_load_settings)

    with TestClient(app) as client:
        response = client.get("/admin/settings")

    assert response.status_code == 200
    assert response.json()[0]["key"] == "platform"


def test_put_admin_settings_updates_entry(monkeypatch):
    session = FakeSession()
    app = build_admin_app(build_user(), session)
    setting = build_setting()

    async def fake_load_setting(*_args):
        return setting

    monkeypatch.setattr("chaoxing.api.admin.load_system_setting", fake_load_setting)

    with TestClient(app) as client:
        response = client.put("/admin/settings/platform", json={"value": {"invite_only": False}})

    assert response.status_code == 200
    assert response.json()["value"]["invite_only"] is False
    assert setting.value["invite_only"] is False
    assert session.commits == 1
