from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.entities import Post, FacebookPage
from app.schemas.schemas import PostRead

router = APIRouter(prefix="/posts", tags=["Posts Monitor"])

@router.get("/", response_model=List[PostRead])
async def list_posts(
    page_id: Optional[int] = Query(None, description="Filter by Facebook Page ID"),
    db: AsyncSession = Depends(get_db)
):
    query = select(Post).order_by(Post.created_at.desc())
    if page_id:
        query = query.where(Post.page_id == page_id)
    result = await db.execute(query)
    return result.scalars().all()

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
