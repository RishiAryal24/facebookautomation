from typing import List
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.entities import FacebookPage, Post, ActionLog, ActionStatus
from app.schemas.schemas import FacebookPageCreate, FacebookPageUpdate, FacebookPageRead
from app.core.security import encrypt_token, decrypt_token
from app.services.meta_client import meta_client

router = APIRouter(prefix="/pages", tags=["Facebook Pages"])

@router.get("/", response_model=List[FacebookPageRead])
async def list_pages(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(FacebookPage).order_by(FacebookPage.created_at.desc()))
    return result.scalars().all()

@router.post("/", response_model=FacebookPageRead)
async def connect_page(page_in: FacebookPageCreate, db: AsyncSession = Depends(get_db)):
    # Check if page already exists
    res = await db.execute(select(FacebookPage).where(FacebookPage.meta_page_id == page_in.meta_page_id))
    existing = res.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Facebook Page is already connected")
    
    # Encrypt token
    enc_token = encrypt_token(page_in.access_token) if page_in.access_token else None
    
    # Fetch page details from Meta if token provided
    page_name = page_in.name
    category = page_in.category
    pic_url = page_in.picture_url

    try:
        meta_info = await meta_client.get_page_info(page_in.meta_page_id, page_in.access_token or "")
        page_name = meta_info.get("name", page_name)
        category = meta_info.get("category", category)
        if "picture" in meta_info and "data" in meta_info["picture"]:
            pic_url = meta_info["picture"]["data"].get("url", pic_url)
    except Exception as e:
        print(f"Meta page info fetch notice: {e}")

    new_page = FacebookPage(
        meta_page_id=page_in.meta_page_id,
        name=page_name,
        category=category,
        picture_url=pic_url,
        access_token_enc=enc_token,
        is_connected=True,
        automation_enabled=page_in.automation_enabled,
        auto_approve_enabled=page_in.auto_approve_enabled,
        auto_like_enabled=page_in.auto_like_enabled,
        default_language=page_in.default_language,
        response_tone=page_in.response_tone,
        brand_context=page_in.brand_context,
        operating_hours_start=page_in.operating_hours_start,
        operating_hours_end=page_in.operating_hours_end,
        max_actions_per_hour=page_in.max_actions_per_hour,
        cooldown_seconds=page_in.cooldown_seconds
    )
    db.add(new_page)
    await db.commit()
    await db.refresh(new_page)

    # Initial sync of posts
    try:
        token = decrypt_token(new_page.access_token_enc) if new_page.access_token_enc else ""
        posts_data = await meta_client.fetch_page_posts(new_page.meta_page_id, token)
        for p in posts_data:
            post = Post(
                meta_post_id=p["id"],
                page_id=new_page.id,
                message=p.get("message", "Post update"),
                permalink_url=p.get("permalink_url"),
                media_url=p.get("full_picture"),
                like_count=p.get("likes", {}).get("summary", {}).get("total_count", 0),
                comment_count=p.get("comments", {}).get("summary", {}).get("total_count", 0)
            )
            db.add(post)
        new_page.last_synced_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(new_page)
    except Exception as err:
        print(f"Initial sync warning: {err}")

    return new_page

@router.get("/{page_id}", response_model=FacebookPageRead)
async def get_page(page_id: int, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(FacebookPage).where(FacebookPage.id == page_id))
    page = res.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    return page

@router.put("/{page_id}", response_model=FacebookPageRead)
async def update_page(page_id: int, page_update: FacebookPageUpdate, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(FacebookPage).where(FacebookPage.id == page_id))
    page = res.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    update_dict = page_update.model_dump(exclude_unset=True)
    if "access_token" in update_dict and update_dict["access_token"]:
        page.access_token_enc = encrypt_token(update_dict.pop("access_token"))

    for key, val in update_dict.items():
        setattr(page, key, val)

    await db.commit()
    await db.refresh(page)
    return page

@router.post("/{page_id}/toggle-automation")
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

@router.post("/{page_id}/sync")
async def sync_page_posts(page_id: int, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(FacebookPage).where(FacebookPage.id == page_id))
    page = res.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    token = decrypt_token(page.access_token_enc) if page.access_token_enc else ""
    posts_data = await meta_client.fetch_page_posts(page.meta_page_id, token)
    
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

@router.delete("/{page_id}")
async def disconnect_page(page_id: int, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(FacebookPage).where(FacebookPage.id == page_id))
    page = res.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    await db.delete(page)
    await db.commit()
    return {"status": "disconnected", "id": page_id}
