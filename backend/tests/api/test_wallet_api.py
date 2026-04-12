from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from chaoxing.db.database import get_db
from chaoxing.models.billing import RechargeOrderStatus
from chaoxing.models.enums import UserRole
from chaoxing.models.user import User
from chaoxing.models.wallet import Wallet, WalletTransaction


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
            obj.id = 41
        now = datetime.now(timezone.utc)
        if getattr(obj, "created_at", None) is None:
            obj.created_at = now
        if getattr(obj, "updated_at", None) is None:
            obj.updated_at = now


def build_wallet_app(user: User, session: FakeSession) -> FastAPI:
    from chaoxing.api.wallet import router as wallet_router
    from chaoxing.auth.dependencies import get_current_active_user

    app = FastAPI()
    app.include_router(wallet_router, prefix="/wallet")

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


def build_wallet(**overrides) -> Wallet:
    data = {
        "id": 12,
        "user_id": 3,
        "balance": 120,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    data.update(overrides)
    return Wallet(**data)


def build_transaction(**overrides) -> WalletTransaction:
    data = {
        "id": 7,
        "wallet_id": 12,
        "user_id": 3,
        "delta": 20,
        "balance_after": 120,
        "reason": "manual_credit",
        "related_run_id": None,
        "metadata_json": {"source": "admin"},
        "created_at": datetime.now(timezone.utc),
    }
    data.update(overrides)
    return WalletTransaction(**data)


def test_get_wallet_returns_current_balance(monkeypatch):
    app = build_wallet_app(build_user(), FakeSession())

    async def fake_get_wallet(*_args):
        return build_wallet()

    monkeypatch.setattr("chaoxing.api.wallet.get_or_create_user_wallet", fake_get_wallet)

    with TestClient(app) as client:
        response = client.get("/wallet")

    assert response.status_code == 200
    assert response.json()["balance"] == 120


def test_get_wallet_transactions_returns_entries(monkeypatch):
    app = build_wallet_app(build_user(), FakeSession())

    async def fake_load_transactions(*_args):
        return [build_transaction()]

    monkeypatch.setattr("chaoxing.api.wallet.load_wallet_transactions", fake_load_transactions)

    with TestClient(app) as client:
        response = client.get("/wallet/transactions")

    assert response.status_code == 200
    assert response.json()[0]["delta"] == 20


def test_post_recharge_creates_pending_order():
    session = FakeSession()
    app = build_wallet_app(build_user(), session)

    with TestClient(app) as client:
        response = client.post(
            "/wallet/recharge",
            json={
                "amount_cents": 1999,
                "requested_credits": 200,
                "payment_channel": "alipay",
                "payment_reference": "trade-001",
            },
        )

    assert response.status_code == 201
    assert response.json()["status"] == RechargeOrderStatus.PENDING.value
    created = session.added[0]
    assert created.user_id == 3
    assert created.amount_cents == 1999
    assert created.requested_credits == 200
    assert session.commits == 1
