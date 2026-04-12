from fastapi import APIRouter

from .accounts import router as accounts_router
from .admin import router as admin_router
from .auth import router as auth_router
from .courses import router as courses_router
from .notifications import router as notifications_router
from .study_runs import router as study_runs_router
from .users import router as users_router
from .wallet import router as wallet_router

router = APIRouter()


@router.get("/")
async def api_root() -> dict[str, str]:
    return {"message": "Chaoxing Web API", "version": "4.0.0-alpha.1"}


router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(accounts_router, prefix="/accounts", tags=["accounts"])
router.include_router(courses_router, prefix="/accounts", tags=["courses"])
router.include_router(study_runs_router, prefix="/study-runs", tags=["study-runs"])
router.include_router(users_router, prefix="/users", tags=["users"])
router.include_router(notifications_router, prefix="/users", tags=["notifications"])
router.include_router(wallet_router, prefix="/wallet", tags=["wallet"])
router.include_router(admin_router, prefix="/admin", tags=["admin"])
