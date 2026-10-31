from typing import List
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.core.database import get_db
from app.models.entities import FacebookPage, Post, ActionLog, ActionStatus, UserRole
from app.schemas.schemas import FacebookPageCreate, FacebookPageUpdate, FacebookPageRead
from app.core.security import encrypt_token
from app.services.meta_client import MetaAPIError, meta_client
from app.api.v1.auth import get_current_user, require_roles

router = APIRouter(
    prefix="/pages",
    tags=["Facebook Pages"],
    dependencies=[Depends(get_current_user)],
)
PAGE_ADMIN_ROLES = (UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.ADMIN)


@router.get("/", response_model=List[FacebookPageRead])
async def list_pages(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(FacebookPage).order_by(FacebookPage.created_at.desc()))
    return result.scalars().all()

@router.post(
    "/",
    response_model=FacebookPageRead,
    dependencies=[Depends(require_roles(*PAGE_ADMIN_ROLES))],
)
async def connect_page(page_in: FacebookPageCreate, db: AsyncSession = Depends(get_db)):
    access_token = page_in.access_token
    result = await db.execute(
        select(FacebookPage).where(FacebookPage.meta_page_id == page_in.meta_page_id)
    )
    existing = result.scalar_one_or_none()

    try:
        credential_info = await meta_client.validate_page_credentials(
            page_in.meta_page_id,
            access_token,
            user_access_token=page_in.user_access_token,
            force_live=True,
        )
    except MetaAPIError as err:
        raise HTTPException(
            status_code=422,
            detail={
                "message": str(err),
                "status": meta_client.validation_failure_status(err),
                "meta_error": err.meta_error or {},
            },
        ) from err

    if credential_info["status"] != "valid":
        raise HTTPException(
            status_code=422,
            detail={"message": "Meta did not verify the Page access token.", "status": "connection_failed"},
        )
    if credential_info.get("tasks") is None:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Provide a temporary User Access Token to verify CREATE_CONTENT. It is not stored.",
                "status": "task_verification_required",
                "meta_error": {},
            },
        )

    meta_info = credential_info["page"]
    picture = meta_info.get("picture", {}).get("data", {})
    now = datetime.now(timezone.utc)
    if existing:
        page = existing
        page.name = meta_info.get("name", page.name)
        page.category = meta_info.get("category", page.category)
        page.picture_url = picture.get("url", page.picture_url)
    else:
        page_data = page_in.model_dump(
            exclude={"access_token", "user_access_token"}
        )
        page_data.update(
            name=meta_info.get("name", page_in.name),
            category=meta_info.get("category", page_in.category),
            picture_url=picture.get("url", page_in.picture_url),
        )
        page = FacebookPage(**page_data)
        db.add(page)

    page.access_token_enc = encrypt_token(access_token)
    page.token_status = "valid"
    page.token_expires_at = credential_info["expires_at"]
    page.meta_app_id = settings.META_APP_ID
    page.last_validated_at = now
    page.granted_permissions = credential_info["permissions"]
    if credential_info.get("tasks") is not None:
        page.page_tasks = credential_info["tasks"]
    page.is_connected = True
    try:
        await db.commit()
    except IntegrityError as err:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This Facebook Page was connected concurrently; reload and try again.",
        ) from err
    await db.refresh(page)
    return page

@router.post(
    "/diagnose-token",
    dependencies=[Depends(require_roles(*PAGE_ADMIN_ROLES))],
)
async def diagnose_page_token(page_in: FacebookPageCreate):
    try:
        return await meta_client.diagnose_page_authentication(
            page_in.meta_page_id,
            page_in.access_token,
            page_in.user_access_token,
        )
    except MetaAPIError as err:
        raise HTTPException(
            status_code=422,
            detail={
                "message": str(err),
                "meta_error": err.meta_error or {},
            },
        ) from err

@router.get("/{page_id}", response_model=FacebookPageRead)
async def get_page(page_id: int, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(FacebookPage).where(FacebookPage.id == page_id))
    page = res.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    return page

@router.put(
    "/{page_id}",
    response_model=FacebookPageRead,
    dependencies=[Depends(require_roles(*PAGE_ADMIN_ROLES))],
)
async def update_page(page_id: int, page_update: FacebookPageUpdate, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(FacebookPage).where(FacebookPage.id == page_id))
    page = res.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    update_dict = page_update.model_dump(exclude_unset=True)
    access_token = update_dict.pop("access_token", None)
    user_access_token = update_dict.pop("user_access_token", None)
    if access_token:
        if access_token.startswith("mock_"):
            raise HTTPException(
                status_code=422,
                detail="A real Page access token is required to replace connected credentials.",
            )
        try:
            credential_info = await meta_client.validate_page_credentials(
                page.meta_page_id,
                access_token,
                user_access_token=user_access_token,
                force_live=True,
            )
        except MetaAPIError as err:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": str(err),
                    "status": meta_client.validation_failure_status(err),
                    "meta_error": err.meta_error or {},
                },
            ) from err
        if credential_info["status"] != "valid":
            raise HTTPException(
                status_code=409,
                detail="A live Page token must be validated before it can replace the stored token.",
            )
        if credential_info.get("tasks") is None:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Provide a temporary User Access Token to verify CREATE_CONTENT. It is not stored.",
                    "status": "task_verification_required",
                    "meta_error": {},
                },
            )
        page.access_token_enc = encrypt_token(access_token)
        page.token_status = credential_info["status"]
        page.token_expires_at = credential_info["expires_at"]
        page.meta_app_id = settings.META_APP_ID
        page.last_validated_at = datetime.now(timezone.utc)
        page.granted_permissions = credential_info["permissions"]
        if credential_info.get("tasks") is not None:
            page.page_tasks = credential_info["tasks"]

    for key, val in update_dict.items():
        setattr(page, key, val)

    await db.commit()
    await db.refresh(page)
    return page

@router.post(
    "/{page_id}/toggle-automation",
    dependencies=[Depends(require_roles(*PAGE_ADMIN_ROLES))],
)
async def toggle_automation(page_id: int, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(FacebookPage).where(FacebookPage.id == page_id))
    page = res.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    page.automation_enabled = not page.automation_enabled
    
    # Audit log
    action_name = "automation_enabled" if page.automation_enabled else "automation_paused"
    log = ActionLog(
        page_id=page.id,
        action_type=action_name,
        status=ActionStatus.SUCCESS,
        details={"page_name": page.name, "active": page.automation_enabled}
    )
    db.add(log)
    await db.commit()
    await db.refresh(page)
    return {"id": page.id, "automation_enabled": page.automation_enabled}


@router.post(
    "/{page_id}/validate-credentials",
    dependencies=[Depends(require_roles(*PAGE_ADMIN_ROLES))],
)
async def validate_page_credentials(page_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(FacebookPage).where(FacebookPage.id == page_id))
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    try:
        access_token = meta_client.get_page_access_token(page, allow_revalidation=True)
    except MetaAPIError as err:
        page.token_status = meta_client.validation_failure_status(err)
        await db.commit()
        raise HTTPException(status_code=409, detail=str(err)) from err
    try:
        credential_info = await meta_client.validate_page_credentials(
            page.meta_page_id,
            access_token,
            force_live=not access_token.startswith("mock_"),
        )
    except MetaAPIError as err:
        page.token_status = meta_client.validation_failure_status(err)
        await db.commit()
        raise HTTPException(
            status_code=422,
            detail={
                "message": str(err),
                "status": page.token_status,
                "meta_error": err.meta_error or {},
            },
        ) from err

    expires_at = credential_info["expires_at"]
    expiring_soon = (
        expires_at is not None
        and expires_at <= datetime.now(timezone.utc) + timedelta(days=7)
    )
    page.token_status = "expiring_soon" if expiring_soon else credential_info["status"]
    page.token_expires_at = credential_info["expires_at"]
    page.meta_app_id = credential_info.get("meta_app_id", settings.META_APP_ID)
    page.last_validated_at = datetime.now(timezone.utc)
    page.granted_permissions = credential_info["permissions"]
    page.page_tasks = credential_info.get("tasks", [])
    await db.commit()
    return {
        "status": page.token_status,
        "expires_at": page.token_expires_at,
        "meta_app_id": page.meta_app_id,
        "last_validated_at": page.last_validated_at,
        "permissions": page.granted_permissions,
        "tasks": page.page_tasks,
    }

@router.post(
    "/{page_id}/sync",
    dependencies=[Depends(require_roles(*PAGE_ADMIN_ROLES))],
)
async def sync_page_posts(page_id: int, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(FacebookPage).where(FacebookPage.id == page_id))
    page = res.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    try:
        token = meta_client.get_page_access_token(page)
    except MetaAPIError as err:
        raise HTTPException(status_code=409, detail=str(err)) from err
    posts_data = await meta_client.fetch_page_posts(
        page.meta_page_id,
        token,
        force_live=not token.startswith("mock_"),
    )
    
    added_count = 0
    for p in posts_data:
        check = await db.execute(select(Post).where(Post.meta_post_id == p["id"]))
        if not check.scalar_one_or_none():
            post = Post(
                meta_post_id=p["id"],
                page_id=page.id,
                message=p.get("message", "Post update"),
                permalink_url=p.get("permalink_url"),
                media_url=p.get("full_picture"),
                like_count=p.get("likes", {}).get("summary", {}).get("total_count", 0),
                comment_count=p.get("comments", {}).get("summary", {}).get("total_count", 0)
            )
            db.add(post)
            added_count += 1

    page.last_synced_at = datetime.now(timezone.utc)
    await db.commit()
    return {"status": "success", "synced_posts": len(posts_data), "new_posts_added": added_count}

@router.delete(
    "/{page_id}",
    dependencies=[Depends(require_roles(*PAGE_ADMIN_ROLES))],
)
async def disconnect_page(page_id: int, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(FacebookPage).where(FacebookPage.id == page_id))
    page = res.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    await db.delete(page)
    await db.commit()
    return {"status": "disconnected", "id": page_id}
