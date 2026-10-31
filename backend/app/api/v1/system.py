from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, StrictBool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import get_db
from app.models.entities import FacebookPage, UserRole
from app.api.v1.auth import get_current_user, require_roles

router = APIRouter(
    prefix="/system",
    tags=["System Configuration"],
    dependencies=[Depends(get_current_user)],
)
ADMIN_ROLES = (UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ADMIN)
REQUIRED_POST_PERMISSIONS = {"pages_manage_posts", "pages_read_engagement"}
REQUIRED_PAGE_TASKS = {"CREATE_CONTENT"}


class SimulationModeUpdate(BaseModel):
    simulation_mode: StrictBool


async def _live_readiness(db: AsyncSession) -> tuple[bool, list[str]]:
    blockers: list[str] = []
    result = await db.execute(
        select(FacebookPage).where(FacebookPage.is_connected.is_(True))
    )
    pages = result.scalars().all()
    if not pages:
        blockers.append("Connect and validate a Facebook Page.")
        return False, blockers

    for page in pages:
        if (
            page.token_status == "valid"
            and page.access_token_enc
            and page.meta_app_id == settings.META_APP_ID
            and REQUIRED_POST_PERMISSIONS.issubset(set(page.granted_permissions or []))
            and REQUIRED_PAGE_TASKS.issubset(set(page.page_tasks or []))
        ):
            return True, []

    blockers.append(
        "At least one connected Page must have a valid token for the configured Meta app, "
        "pages_manage_posts, pages_read_engagement, and CREATE_CONTENT."
    )
    return False, blockers


@router.get("/simulation-mode")
async def get_simulation_mode(db: AsyncSession = Depends(get_db)):
    live_ready, blockers = await _live_readiness(db)
    return {
        "simulation_mode": settings.SIMULATION_MODE,
        "live_ready": live_ready,
        "live_blockers": blockers,
    }


@router.put(
    "/simulation-mode",
    dependencies=[Depends(require_roles(*ADMIN_ROLES))],
)
async def update_simulation_mode(
    request: SimulationModeUpdate,
    db: AsyncSession = Depends(get_db),
):
    if not request.simulation_mode:
        live_ready, blockers = await _live_readiness(db)
        if not live_ready:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Live mode is locked until the Facebook Page is validated.",
                    "blockers": blockers,
                },
            )

    settings.SIMULATION_MODE = request.simulation_mode
    live_ready, blockers = await _live_readiness(db)
    return {
        "simulation_mode": settings.SIMULATION_MODE,
        "live_ready": live_ready,
        "live_blockers": blockers,
    }
