from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import get_current_active_user
from ..core.services.auth_service import AuthService
from ..core.services.course_service import CourseService
from ..core.services.session_service import SessionService
from ..db.database import get_db
from ..models.chaoxing_account import ChaoxingAccount
from ..models.user import User
from .accounts import build_login_payload, load_user_account

router = APIRouter()


@router.get("/{account_id}/courses")
async def list_account_courses(
    account_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[dict[str, Any]]:
    account = await load_user_account(db, current_user, account_id)
    return await get_account_courses(account)


@router.get("/{account_id}/courses/{course_id}/chapters")
async def get_course_chapters(
    account_id: int,
    course_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    account = await load_user_account(db, current_user, account_id)
    return await get_account_chapters(account, course_id)


async def get_account_courses(account: ChaoxingAccount) -> list[dict[str, Any]]:
    session_service = SessionService()
    auth_service = AuthService(session_service)
    course_service = CourseService(session_service)

    try:
        login_payload, login_with_cookies = build_login_payload(account)
        login_result = await auth_service.login(str(account.id), login_payload, login_with_cookies)
        if login_result["status"] != "success":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=login_result["message"])
        return await course_service.get_course_list(str(account.id))
    finally:
        await session_service.close_all()


async def get_account_chapters(account: ChaoxingAccount, course_id: str) -> dict[str, Any]:
    session_service = SessionService()
    auth_service = AuthService(session_service)
    course_service = CourseService(session_service)

    try:
        login_payload, login_with_cookies = build_login_payload(account)
        login_result = await auth_service.login(str(account.id), login_payload, login_with_cookies)
        if login_result["status"] != "success":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=login_result["message"])

        courses = await course_service.get_course_list(str(account.id))
        course = next(
            (
                item
                for item in courses
                if str(item.get("courseId") or item.get("course_id") or "") == course_id
            ),
            None,
        )
        if course is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

        normalized_course = {
            **course,
            "course_id": course.get("course_id") or course.get("courseId"),
            "clazz_id": course.get("clazz_id") or course.get("clazzId"),
        }
        points = await course_service.get_course_points(str(account.id), normalized_course)
        return {
            "courseId": normalized_course["course_id"],
            "clazzId": normalized_course["clazz_id"],
            "cpi": normalized_course.get("cpi"),
            "title": normalized_course.get("title"),
            "hasLocked": any(point.get("need_unlock") for point in points),
            "points": points,
        }
    finally:
        await session_service.close_all()
