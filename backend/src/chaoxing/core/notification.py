"""
Notification service module.

Supports multiple notification providers: ServerChan, Qmsg, Bark, Telegram.
Uses httpx (async) for all HTTP calls.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import httpx

from ..utils import get_logger

logger = get_logger(__name__)


class NotificationProvider(ABC):
    """Base class for notification providers."""

    @abstractmethod
    async def send(self, title: str, content: str) -> bool:
        """Send a notification. Returns True on success."""


class ServerChanProvider(NotificationProvider):
    """Server酱 push notification provider."""

    def __init__(self, url: str):
        self.url = url

    async def send(self, title: str, content: str) -> bool:
        payload = {"text": title, "desp": content}
        headers = {"Content-Type": "application/json;charset=utf-8"}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(self.url, json=payload, headers=headers)
                resp.raise_for_status()
                logger.info("ServerChan notification sent successfully")
                return True
        except Exception as exc:
            logger.error("ServerChan notification failed: %s", exc)
            return False


class QmsgProvider(NotificationProvider):
    """Qmsg QQ message notification provider."""

    def __init__(self, url: str):
        self.url = url

    async def send(self, title: str, content: str) -> bool:
        message = f"{title}\n{content}" if content else title
        params = {"msg": message}
        headers = {"Content-Type": "application/json;charset=utf-8"}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(self.url, params=params, headers=headers)
                resp.raise_for_status()
                logger.info("Qmsg notification sent successfully")
                return True
        except Exception as exc:
            logger.error("Qmsg notification failed: %s", exc)
            return False


class BarkProvider(NotificationProvider):
    """Bark iOS push notification provider."""

    def __init__(self, url: str):
        self.url = url

    async def send(self, title: str, content: str) -> bool:
        params = {"title": title, "body": content}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(self.url, params=params)
                resp.raise_for_status()
                logger.info("Bark notification sent successfully")
                return True
        except Exception as exc:
            logger.error("Bark notification failed: %s", exc)
            return False


class TelegramProvider(NotificationProvider):
    """Telegram Bot notification provider."""

    def __init__(self, url: str, chat_id: str):
        self.url = url
        self.chat_id = chat_id

    async def send(self, title: str, content: str) -> bool:
        text = f"<b>{title}</b>\n{content}" if content else f"<b>{title}</b>"
        payload = {"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(self.url, data=payload)
                resp.raise_for_status()
                result = resp.json()
                if result.get("ok"):
                    logger.info("Telegram notification sent successfully")
                    return True
                logger.error("Telegram notification failed: %s", result)
                return False
        except Exception as exc:
            logger.error("Telegram notification failed: %s", exc)
            return False


PROVIDER_MAP = {
    "serverchan": ServerChanProvider,
    "qmsg": QmsgProvider,
    "bark": BarkProvider,
    "telegram": TelegramProvider,
}


def build_provider(provider_type: str, settings: dict[str, Any]) -> NotificationProvider | None:
    """Construct a provider instance from type string and settings dict."""
    provider_type = provider_type.lower()
    url = settings.get("url", "")

    if provider_type == "serverchan":
        return ServerChanProvider(url=url) if url else None
    if provider_type == "qmsg":
        return QmsgProvider(url=url) if url else None
    if provider_type == "bark":
        return BarkProvider(url=url) if url else None
    if provider_type == "telegram":
        chat_id = settings.get("chat_id", "")
        return TelegramProvider(url=url, chat_id=chat_id) if url and chat_id else None

    logger.warning("Unknown notification provider type: %s", provider_type)
    return None


class NotificationService:
    """Manages sending notifications to all enabled providers for a user."""

    def __init__(self, configs: list[dict[str, Any]] | None = None):
        self.providers: list[NotificationProvider] = []
        if configs:
            for cfg in configs:
                if not cfg.get("enabled", True):
                    continue
                provider = build_provider(
                    cfg.get("provider", ""),
                    cfg.get("settings_json", {}),
                )
                if provider is not None:
                    self.providers.append(provider)

    async def send_all(self, title: str, content: str) -> dict[str, bool]:
        """Send notification to all registered providers. Returns per-provider results."""
        results: dict[str, bool] = {}
        for provider in self.providers:
            name = type(provider).__name__
            results[name] = await provider.send(title, content)
        return results

    async def send_test(self) -> dict[str, bool]:
        """Send a test notification to all providers."""
        return await self.send_all(
            "测试通知 / Test Notification",
            "如果你收到此消息，说明通知配置正确。\nIf you received this message, "
            "your notification config is working.",
        )
