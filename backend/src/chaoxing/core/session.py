from __future__ import annotations

import asyncio
from collections.abc import Mapping

import httpx

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/118.0.0.0 Safari/537.36"
    ),
    "sec-ch-ua": '"Chromium";v="118", "Google Chrome";v="118", "Not=A?Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}

DEFAULT_TIMEOUT = httpx.Timeout(timeout=10.0, connect=5.0)


class SessionManager:
    def __init__(self) -> None:
        self._clients: dict[str, httpx.AsyncClient] = {}
        self._lock = asyncio.Lock()

    async def get_client(self, account_id: str) -> httpx.AsyncClient:
        async with self._lock:
            client = self._clients.get(account_id)
            if client is None or client.is_closed:
                client = httpx.AsyncClient(
                    headers=DEFAULT_HEADERS,
                    timeout=DEFAULT_TIMEOUT,
                    transport=httpx.AsyncHTTPTransport(retries=3),
                )
                self._clients[account_id] = client
            return client

    async def set_cookies(self, account_id: str, cookies: Mapping[str, str]) -> None:
        client = await self.get_client(account_id)
        client.cookies.update(cookies)

    async def get_cookies(self, account_id: str) -> dict[str, str]:
        client = await self.get_client(account_id)
        return dict(client.cookies)

    async def close_client(self, account_id: str) -> None:
        async with self._lock:
            client = self._clients.pop(account_id, None)

        if client is not None:
            await client.aclose()

    async def close_all(self) -> None:
        async with self._lock:
            clients = list(self._clients.values())
            self._clients.clear()

        for client in clients:
            await client.aclose()
