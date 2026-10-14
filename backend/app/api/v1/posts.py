from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.entities import Post, FacebookPage
from app.schemas.schemas import PostRead, PostDraftGenerateRequest, PostPublishRequest
from app.services.automation_runner import automation_engine

router = APIRouter(prefix="/posts", tags=["Posts Monitor & Daily Creator"])

@router.get("/", response_model=List[PostRead])
async def list_posts(
    page_id: Optional[int] = Query(None, description="Filter by Facebook Page ID"),
    status: Optional[str] = Query(None, description="Filter by status: published, draft, failed"),
    db: AsyncSession = Depends(get_db)
):
    query = select(Post).order_by(Post.created_at.desc())
    if page_id:
        query = query.where(Post.page_id == page_id)
    if status:
        query = query.where(Post.status == status)
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/drafts", response_model=List[PostRead])
async def list_draft_posts(
    page_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve all AI-generated post drafts waiting for review."""
    query = select(Post).where(Post.status == "draft").order_by(Post.created_at.desc())
    if page_id:
        query = query.where(Post.page_id == page_id)
    result = await db.execute(query)
    return result.scalars().all()

@router.post("/generate-draft", response_model=PostRead)
async def generate_post_draft(
    draft_req: PostDraftGenerateRequest,
    db: AsyncSession = Depends(get_db)
):
    """Trigger AI generation of a new daily Facebook post draft."""
    res_page = await db.execute(select(FacebookPage).where(FacebookPage.id == draft_req.page_id))
    page = res_page.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    post = await automation_engine.generate_daily_post(
        db=db,
        page=page,
        topic=draft_req.topic,
        language=draft_req.language or "ne",
        tone=draft_req.tone or "promotional",
        auto_publish=draft_req.auto_publish
    )
    return post

@router.post("/{post_id}/publish", response_model=PostRead)
async def publish_draft(
    post_id: int,
    pub_req: PostPublishRequest,
    db: AsyncSession = Depends(get_db)
):
    """Publish an AI-generated draft post to Facebook."""
    res = await db.execute(select(Post).options(selectinload(Post.page)).where(Post.id == post_id))
    post = res.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    success = await automation_engine.publish_draft_post(
        db=db,
        post=post,
        edited_message=pub_req.edited_message,
        media_url=pub_req.media_url
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to publish post to Facebook")

    return post

@router.get("/{post_id}", response_model=PostRead)
async def get_post(post_id: int, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Post).where(Post.id == post_id))
    post = res.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post

@router.post("/{post_id}/toggle-monitoring")
async def toggle_monitoring(post_id: int, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Post).where(Post.id == post_id))
    post = res.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    post.is_monitored = not post.is_monitored
    await db.commit()
    await db.refresh(post)
    return {"id": post.id, "is_monitored": post.is_monitored}

@router.delete("/{post_id}")
async def delete_post(post_id: int, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Post).where(Post.id == post_id))
    post = res.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    await db.delete(post)
    await db.commit()
    return {"status": "deleted", "id": post_id}
