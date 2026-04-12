from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import get_current_active_user
from ..core.notification import NotificationService
from ..db.database import get_db
from ..models.notification_config import NotificationConfig, NotificationProviderType
from ..models.user import User

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class NotificationProviderConfig(BaseModel):
    id: int | None = None
    provider: NotificationProviderType
    enabled: bool = True
    name: str = ""
    settings_json: dict[str, Any] = {}


class NotificationConfigResponse(BaseModel):
    providers: list[NotificationProviderConfig]


class NotificationConfigUpdate(BaseModel):
    providers: list[NotificationProviderConfig]


class TestNotificationResponse(BaseModel):
    results: dict[str, bool]


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _load_user_configs(
    db: AsyncSession, user: User
) -> list[NotificationConfig]:
    result = await db.execute(
        select(NotificationConfig)
        .where(NotificationConfig.user_id == user.id)
        .order_by(NotificationConfig.id.asc())
    )
    return list(result.scalars().all())


def _serialize_config(cfg: NotificationConfig) -> NotificationProviderConfig:
    return NotificationProviderConfig(
        id=cfg.id,
        provider=cfg.provider,
        enabled=cfg.enabled,
        name=cfg.name,
        settings_json=cfg.settings_json,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/notification-config", response_model=NotificationConfigResponse)
async def get_notification_config(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> NotificationConfigResponse:
    configs = await _load_user_configs(db, current_user)
    return NotificationConfigResponse(
        providers=[_serialize_config(c) for c in configs],
    )


@router.put("/notification-config", response_model=NotificationConfigResponse)
async def update_notification_config(
    payload: NotificationConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> NotificationConfigResponse:
    # Remove all existing configs for this user and replace with the new set
    existing = await _load_user_configs(db, current_user)
    for cfg in existing:
        await db.delete(cfg)
    await db.flush()

    new_configs: list[NotificationConfig] = []
    for item in payload.providers:
        cfg = NotificationConfig(
            user_id=current_user.id,
            provider=item.provider,
            enabled=item.enabled,
            name=item.name,
            settings_json=item.settings_json,
        )
        db.add(cfg)
        new_configs.append(cfg)

    await db.commit()
    for cfg in new_configs:
        await db.refresh(cfg)

    return NotificationConfigResponse(
        providers=[_serialize_config(c) for c in new_configs],
    )


@router.post("/notification-config/test", response_model=TestNotificationResponse)
async def test_notification(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> TestNotificationResponse:
    configs = await _load_user_configs(db, current_user)
    if not configs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No notification providers configured",
        )

    config_dicts = [
        {
            "provider": cfg.provider.value,
            "enabled": cfg.enabled,
            "settings_json": cfg.settings_json,
        }
        for cfg in configs
    ]
    service = NotificationService(config_dicts)
    results = await service.send_test()
    return TestNotificationResponse(results=results)
