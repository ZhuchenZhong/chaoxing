from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import get_current_active_user
from ..db.database import get_db
from ..models.study_run import StudyRun, StudyRunEvent, StudyRunStatus
from ..models.user import User
from ..tasks.study_tasks import process_study_run
from .accounts import load_user_account

router = APIRouter()


class StudyRunCreate(BaseModel):
    account_id: int
    course_ids: list[str] = Field(default_factory=list)
    profile_id: int | None = None


class StudyRunEventResponse(BaseModel):
    id: int
    run_id: int
    level: str
    message: str
    detail_json: dict[str, Any]
    created_at: Any

    model_config = ConfigDict(from_attributes=True)


class StudyRunResponse(BaseModel):
    id: int
    user_id: int
    account_id: int
    profile_id: int | None
    course_ids: list[str]
    status: StudyRunStatus
    celery_task_id: str | None
    progress_json: dict[str, Any]
    started_at: Any
    finished_at: Any
    created_at: Any
    updated_at: Any

    model_config = ConfigDict(from_attributes=True)


class StudyRunDetailResponse(StudyRunResponse):
    events: list[StudyRunEventResponse]


@router.post("", response_model=StudyRunResponse, status_code=status.HTTP_201_CREATED)
async def create_study_run(
    payload: StudyRunCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> StudyRun:
    await load_user_account(db, current_user, payload.account_id)
    run = StudyRun(
        user_id=current_user.id,
        account_id=payload.account_id,
        profile_id=payload.profile_id,
        course_ids=payload.course_ids,
        status=StudyRunStatus.QUEUED,
        progress_json={},
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    run.celery_task_id = enqueue_study_run(run)
    await db.commit()
    await db.refresh(run)
    return run


@router.get("", response_model=list[StudyRunResponse])
async def list_study_runs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[StudyRun]:
    return await load_user_runs(db, current_user)


@router.get("/{run_id}", response_model=StudyRunDetailResponse)
async def get_study_run(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> StudyRunDetailResponse:
    run = await load_user_run(db, current_user, run_id)
    events = await load_run_events(db, run)
    return serialize_run_detail(run, events)


@router.post("/{run_id}/cancel", response_model=StudyRunResponse)
async def cancel_study_run(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> StudyRun:
    run = await load_user_run(db, current_user, run_id)
    if run.status not in (StudyRunStatus.QUEUED, StudyRunStatus.RUNNING):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot cancel run in '{run.status.value}' state",
        )
    # Set STOPPING so the running task sees the flag on its next check
    run.status = StudyRunStatus.STOPPING if run.status == StudyRunStatus.RUNNING else StudyRunStatus.CANCELLED
    await db.commit()
    # Revoke the Celery task (terminate=False lets the task finish its current step)
    if run.celery_task_id:
        try:
            from ..tasks.celery_app import celery_app

            celery_app.control.revoke(run.celery_task_id, terminate=False)
        except Exception:
            pass  # best-effort revoke
    await db.refresh(run)
    return run


def enqueue_study_run(run: StudyRun) -> str | None:
    """Dispatch the Celery task for a study run."""
    task_result = process_study_run.delay(run.id)
    return getattr(task_result, "id", None)


async def load_user_runs(db: AsyncSession, current_user: User) -> list[StudyRun]:
    result = await db.execute(
        select(StudyRun)
        .where(StudyRun.user_id == current_user.id)
        .order_by(StudyRun.created_at.desc(), StudyRun.id.desc())
    )
    return list(result.scalars().all())


async def load_user_run(db: AsyncSession, current_user: User, run_id: int) -> StudyRun:
    result = await db.execute(
        select(StudyRun).where(StudyRun.user_id == current_user.id, StudyRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study run not found")
    return run


async def load_run_events(db: AsyncSession, run: StudyRun) -> list[StudyRunEvent]:
    result = await db.execute(
        select(StudyRunEvent)
        .where(StudyRunEvent.run_id == run.id)
        .order_by(StudyRunEvent.created_at.asc(), StudyRunEvent.id.asc())
    )
    return list(result.scalars().all())


def serialize_run_detail(
    run: StudyRun,
    events: list[StudyRunEvent],
) -> StudyRunDetailResponse:
    payload = StudyRunResponse.model_validate(run).model_dump()
    payload["events"] = [StudyRunEventResponse.model_validate(event) for event in events]
    return StudyRunDetailResponse(**payload)
