import importlib
import sys

import pytest


def test_access_token_round_trip_returns_payload():
    from chaoxing.auth.utils import create_access_token, verify_token

    token = create_access_token({"sub": "42", "scope": "user"})
    payload = verify_token(token)

    assert payload is not None
    assert payload["sub"] == "42"
    assert payload["scope"] == "user"


@pytest.mark.asyncio
async def test_get_db_yields_async_session(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./test-foundation.db")

    for module_name in [
        "chaoxing.config",
        "chaoxing.config.settings",
        "chaoxing.db",
        "chaoxing.db.database",
    ]:
        sys.modules.pop(module_name, None)

    database = importlib.import_module("chaoxing.db.database")

    session_generator = database.get_db()
    session = await anext(session_generator)

    assert session.__class__.__name__ == "AsyncSession"

    await session_generator.aclose()
