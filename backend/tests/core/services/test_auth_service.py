from unittest.mock import AsyncMock, Mock, patch

import pytest

from chaoxing.core.chaoxing.client import ChaoxingLoginResult
from chaoxing.core.chaoxing.exceptions import ChaoxingLoginError
from chaoxing.core.services.auth_service import AuthService


@pytest.mark.asyncio
async def test_auth_service_login_with_password():
    session_service = Mock()
    session_service.session_manager = Mock()

    auth_service = AuthService(session_service)
    account = {"username": "test", "password": "test123"}

    with patch("chaoxing.core.services.auth_service.ChaoxingClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client

        login_result = ChaoxingLoginResult(
            account_id="account_1",
            auth_type="password",
            message="登录成功",
            cookies={"test": "cookie"},
        )
        mock_client.login_with_password.return_value = login_result

        result = await auth_service.login("account_1", account)
        assert result["status"] == "success"
        assert result["message"] == "登录成功"
        assert result["data"] == login_result


@pytest.mark.asyncio
async def test_auth_service_login_error():
    session_service = Mock()
    session_service.session_manager = Mock()

    auth_service = AuthService(session_service)
    account = {"username": "test", "password": "wrong"}

    with patch("chaoxing.core.services.auth_service.ChaoxingClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client.login_with_password.side_effect = ChaoxingLoginError("Invalid credentials")

        result = await auth_service.login("account_1", account)
        assert result["status"] == "error"
        assert result["message"] == "Invalid credentials"
