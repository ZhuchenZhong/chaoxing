from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import get_current_active_user
from ..auth.schemas import UserPublic, UserUpdate
from ..auth.utils import get_password_hash
from ..db.database import get_db
from ..models.enums import NotOpenAction
from ..models.study_profile import StudyProfile
from ..models.user import User

router = APIRouter()


class StudyConfigResponse(BaseModel):
    profile_name: str
    speed: float
    notopen_action: NotOpenAction
    submit_config: dict


class StudyConfigUpdate(BaseModel):
    speed: float | None = None
    notopen_action: NotOpenAction | None = None
    submit_config: dict | None = None


class TikuConfigResponse(BaseModel):
    profile_name: str
    tiku_config: dict


class TikuConfigUpdate(BaseModel):
    tiku_config: dict


@router.get("/profile", response_model=UserPublic)
async def get_profile(current_user: User = Depends(get_current_active_user)) -> User:
    return current_user


@router.put("/profile", response_model=UserPublic)
async def update_profile(
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> User:
    if payload.email is not None:
        current_user.email = payload.email
    if payload.username is not None:
        current_user.username = payload.username
    if payload.display_name is not None:
        current_user.display_name = payload.display_name
    if payload.password is not None:
        current_user.password_hash = get_password_hash(payload.password)

    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.get("/study-config", response_model=StudyConfigResponse)
async def get_study_config(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> StudyConfigResponse:
    profile = await get_or_create_default_profile(db, current_user)
    return serialize_study_config(profile)


@router.put("/study-config", response_model=StudyConfigResponse)
async def update_study_config(
    payload: StudyConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> StudyConfigResponse:
    profile = await get_or_create_default_profile(db, current_user)
    if payload.speed is not None:
        profile.speed = Decimal(str(payload.speed))
    if payload.notopen_action is not None:
        profile.notopen_action = payload.notopen_action
    if payload.submit_config is not None:
        profile.submit_config = payload.submit_config

    await db.commit()
    await db.refresh(profile)
    return serialize_study_config(profile)


@router.get("/tiku-config", response_model=TikuConfigResponse)
async def get_tiku_config(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> TikuConfigResponse:
    profile = await get_or_create_default_profile(db, current_user)
    return serialize_tiku_config(profile)


@router.put("/tiku-config", response_model=TikuConfigResponse)
async def update_tiku_config(
    payload: TikuConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> TikuConfigResponse:
    profile = await get_or_create_default_profile(db, current_user)
    profile.tiku_config = payload.tiku_config
    await db.commit()
    await db.refresh(profile)
    return serialize_tiku_config(profile)


async def get_or_create_default_profile(db: AsyncSession, current_user: User) -> StudyProfile:
    result = await db.execute(
        select(StudyProfile).where(
            StudyProfile.user_id == current_user.id,
            StudyProfile.name == "default",
        )
    )
    profile = result.scalar_one_or_none()
    if profile is not None:
        return profile

    profile = StudyProfile(
        user_id=current_user.id,
        name="default",
        speed=Decimal("1.00"),
        notopen_action=NotOpenAction.RETRY,
        tiku_config={},
        submit_config={},
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


def serialize_study_config(profile: StudyProfile) -> StudyConfigResponse:
    return StudyConfigResponse(
        profile_name=profile.name,
        speed=float(profile.speed),
        notopen_action=profile.notopen_action,
        submit_config=profile.submit_config,
    )


def serialize_tiku_config(profile: StudyProfile) -> TikuConfigResponse:
    return TikuConfigResponse(
        profile_name=profile.name,
        tiku_config=profile.tiku_config,
    )
