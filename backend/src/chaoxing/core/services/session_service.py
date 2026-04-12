from typing import Dict

import httpx

from ..session import SessionManager


class SessionService:
    def __init__(self):
        self.session_manager = SessionManager()

    async def get_client(self, account_id: str) -> httpx.AsyncClient:
        return await self.session_manager.get_client(account_id)

    async def set_cookies(self, account_id: str, cookies: Dict[str, str]):
        await self.session_manager.set_cookies(account_id, cookies)

    async def get_cookies(self, account_id: str) -> Dict[str, str]:
        return await self.session_manager.get_cookies(account_id)

    async def close_client(self, account_id: str):
        await self.session_manager.close_client(account_id)

    async def close_all(self):
        await self.session_manager.close_all()
