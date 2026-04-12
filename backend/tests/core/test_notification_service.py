"""Tests for notification service — provider dispatch and error handling."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from chaoxing.core.notification import (
    BarkProvider,
    NotificationService,
    QmsgProvider,
    ServerChanProvider,
    TelegramProvider,
    build_provider,
)


# ---------------------------------------------------------------------------
# Provider factory
# ---------------------------------------------------------------------------


def test_build_provider_returns_serverchan_with_url():
    provider = build_provider("serverchan", {"url": "https://sc.example.com/send"})
    assert isinstance(provider, ServerChanProvider)
    assert provider.url == "https://sc.example.com/send"


def test_build_provider_returns_none_without_url():
    assert build_provider("serverchan", {}) is None
    assert build_provider("qmsg", {"url": ""}) is None


def test_build_provider_telegram_requires_chat_id():
    assert build_provider("telegram", {"url": "https://api.telegram.org/bot123"}) is None
    provider = build_provider(
        "telegram",
        {"url": "https://api.telegram.org/bot123", "chat_id": "12345"},
    )
    assert isinstance(provider, TelegramProvider)
    assert provider.chat_id == "12345"


def test_build_provider_returns_none_for_unknown_type():
    assert build_provider("wechat", {"url": "https://example.com"}) is None


def test_build_provider_all_types():
    assert isinstance(build_provider("qmsg", {"url": "https://q.example.com"}), QmsgProvider)
    assert isinstance(build_provider("bark", {"url": "https://b.example.com"}), BarkProvider)


# ---------------------------------------------------------------------------
# NotificationService filtering
# ---------------------------------------------------------------------------


def test_service_skips_disabled_providers():
    configs = [
        {"provider": "serverchan", "enabled": False, "settings_json": {"url": "https://sc.example.com"}},
        {"provider": "bark", "enabled": True, "settings_json": {"url": "https://b.example.com"}},
    ]
    service = NotificationService(configs)
    assert len(service.providers) == 1
    assert isinstance(service.providers[0], BarkProvider)


def test_service_with_no_configs():
    service = NotificationService(None)
    assert service.providers == []

    service = NotificationService([])
    assert service.providers == []


# ---------------------------------------------------------------------------
# Async send — mocked HTTP
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_serverchan_send_success():
    provider = ServerChanProvider(url="https://sctapi.ftqq.com/test.send")

    with patch("chaoxing.core.notification.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        resp = httpx.Response(200, json={"code": 0}, request=httpx.Request("POST", "https://sctapi.ftqq.com/test.send"))
        mock_client.post.return_value = resp

        result = await provider.send("Test Title", "Test Content")

    assert result is True
    mock_client.post.assert_called_once()
    call_kwargs = mock_client.post.call_args
    assert call_kwargs[1]["json"]["text"] == "Test Title"
    assert call_kwargs[1]["json"]["desp"] == "Test Content"


@pytest.mark.asyncio
async def test_serverchan_send_failure_returns_false():
    provider = ServerChanProvider(url="https://sctapi.ftqq.com/test.send")

    with patch("chaoxing.core.notification.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.post.side_effect = httpx.HTTPError("Connection refused")

        result = await provider.send("Title", "Content")

    assert result is False


@pytest.mark.asyncio
async def test_telegram_send_checks_ok_field():
    provider = TelegramProvider(url="https://api.telegram.org/bot123/sendMessage", chat_id="999")

    with patch("chaoxing.core.notification.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.post.return_value = httpx.Response(200, json={"ok": True}, request=httpx.Request("POST", "https://api.telegram.org/bot123/sendMessage"))

        result = await provider.send("Alert", "Body")

    assert result is True

    # Now test when ok=False
    with patch("chaoxing.core.notification.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.post.return_value = httpx.Response(200, json={"ok": False}, request=httpx.Request("POST", "https://api.telegram.org/bot123/sendMessage"))

        result = await provider.send("Alert", "Body")

    assert result is False


@pytest.mark.asyncio
async def test_send_all_dispatches_to_all_providers():
    configs = [
        {"provider": "serverchan", "enabled": True, "settings_json": {"url": "https://sc.example.com"}},
        {"provider": "bark", "enabled": True, "settings_json": {"url": "https://b.example.com"}},
    ]
    service = NotificationService(configs)

    # Mock all providers' send methods
    for p in service.providers:
        p.send = AsyncMock(return_value=True)

    results = await service.send_all("Title", "Content")

    assert len(results) == 2
    assert all(v is True for v in results.values())
    for p in service.providers:
        p.send.assert_called_once_with("Title", "Content")


@pytest.mark.asyncio
async def test_send_all_partial_failure():
    configs = [
        {"provider": "serverchan", "enabled": True, "settings_json": {"url": "https://sc.example.com"}},
        {"provider": "bark", "enabled": True, "settings_json": {"url": "https://b.example.com"}},
    ]
    service = NotificationService(configs)

    service.providers[0].send = AsyncMock(return_value=True)
    service.providers[1].send = AsyncMock(return_value=False)

    results = await service.send_all("Title", "Content")

    assert results["ServerChanProvider"] is True
    assert results["BarkProvider"] is False
