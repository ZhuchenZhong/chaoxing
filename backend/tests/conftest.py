"""Shared test fixtures for the chaoxing backend test suite."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from chaoxing.db.database import Base
from chaoxing.models.enums import ChaoxingAuthType, UserRole
from chaoxing.models.user import User
from chaoxing.models.chaoxing_account import ChaoxingAccount
from chaoxing.models.study_run import StudyRun, StudyRunStatus
from chaoxing.core.chaoxing.crypto import AESCipher


@pytest.fixture
async def db_session_factory(tmp_path: Path):
    """In-memory SQLite DB with all tables created."""
    db_path = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest.fixture
def make_user():
    """Factory for User instances with sensible defaults."""

    def _make(**overrides) -> User:
        data = {
            "email": "test@example.com",
            "username": "tester",
            "display_name": "Tester",
            "password_hash": "hashed",
            "role": UserRole.USER,
            "is_active": True,
            "must_change_password": False,
        }
        data.update(overrides)
        return User(**data)

    return _make


@pytest.fixture
def make_account():
    """Factory for ChaoxingAccount instances."""
    cipher = AESCipher()

    def _make(user_id: int = 1, **overrides) -> ChaoxingAccount:
        data = {
            "user_id": user_id,
            "display_name": "Test Account",
            "auth_type": ChaoxingAuthType.PASSWORD,
            "username_encrypted": cipher.encrypt("alice"),
            "password_encrypted": cipher.encrypt("secret"),
            "is_login_valid": False,
        }
        data.update(overrides)
        return ChaoxingAccount(**data)

    return _make
