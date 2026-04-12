import pytest

from chaoxing.core.session import SessionManager


@pytest.mark.anyio
async def test_session_manager_isolates_clients_by_account_id() -> None:
    manager = SessionManager()

    account_a_client = await manager.get_client("account-a")
    same_account_client = await manager.get_client("account-a")
    account_b_client = await manager.get_client("account-b")

    assert account_a_client is same_account_client
    assert account_a_client is not account_b_client

    await account_a_client.aclose()
    await account_b_client.aclose()


@pytest.mark.anyio
async def test_session_manager_sets_and_gets_cookies_per_account() -> None:
    manager = SessionManager()

    await manager.set_cookies("account-a", {"session": "token-a", "route": "node-1"})
    await manager.set_cookies("account-b", {"session": "token-b"})

    assert await manager.get_cookies("account-a") == {
        "session": "token-a",
        "route": "node-1",
    }
    assert await manager.get_cookies("account-b") == {"session": "token-b"}

    await (await manager.get_client("account-a")).aclose()
    await (await manager.get_client("account-b")).aclose()
