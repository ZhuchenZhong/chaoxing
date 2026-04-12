from __future__ import annotations

import json
from typing import Any

from ..chaoxing.client import ChaoxingClient
from ..chaoxing.exceptions import ChaoxingAuthError, ChaoxingLoginError
from .session_service import SessionService


class AuthService:
    def __init__(self, session_service: SessionService):
        self.session_service = session_service

    def _get_client(self, account_id: str) -> ChaoxingClient:
        return ChaoxingClient(
            account_id=account_id,
            session_manager=self.session_service.session_manager,
        )

    async def login(
        self, account_id: str, account: dict[str, str], login_with_cookies: bool = False
    ) -> dict[str, Any]:
        client = self._get_client(account_id)

        if login_with_cookies:
            return await self._login_with_cookies(account, client)
        return await self._login_with_password(account, client)

    async def _login_with_password(
        self, account: dict[str, str], client: ChaoxingClient
    ) -> dict[str, Any]:
        try:
            result = await client.login_with_password(account["username"], account["password"])
            return {"status": "success", "message": "登录成功", "data": result}
        except (ChaoxingLoginError, ChaoxingAuthError) as exc:
            return {"status": "error", "message": str(exc)}

    async def _login_with_cookies(
        self, account: dict[str, str], client: ChaoxingClient
    ) -> dict[str, Any]:
        try:
            cookies = json.loads(account.get("cookies", "{}"))
            result = await client.login_with_cookies(cookies)
            return {"status": "success", "message": "Cookie登录成功", "data": result}
        except (ChaoxingLoginError, ChaoxingAuthError) as exc:
            return {"status": "error", "message": str(exc)}

    async def validate_session(self, account_id: str) -> bool:
        client = self._get_client(account_id)
        return await client.validate_cookie_session()
