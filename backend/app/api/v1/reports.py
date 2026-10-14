from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update

from app.core.database import get_db
from app.models.entities import (
    FacebookPage, Post, Comment, CommentStatus,
    ActionLog, ActionStatus
)
from app.schemas.schemas import DashboardMetrics, ActionLogRead

router = APIRouter(prefix="/reports", tags=["Reports & Analytics"])

@router.get("/metrics", response_model=DashboardMetrics)
async def get_metrics(db: AsyncSession = Depends(get_db)):
    """Fetch high-level KPI metrics for the executive dashboard."""
    # Pages
    res_pages = await db.execute(select(func.count(FacebookPage.id)))
    total_pages = res_pages.scalar() or 0

    # Posts
    res_posts = await db.execute(select(func.count(Post.id)))
    total_posts = res_posts.scalar() or 0

    # Comments
    res_comments = await db.execute(select(func.count(Comment.id)))
    total_comments = res_comments.scalar() or 0

    # Pending Approvals
    res_pending = await db.execute(
        select(func.count(Comment.id)).where(Comment.status == CommentStatus.PENDING_APPROVAL)
    )
    pending_count = res_pending.scalar() or 0

    # Published
    res_published = await db.execute(
        select(func.count(Comment.id)).where(Comment.status == CommentStatus.PUBLISHED)
    )
    published_count = res_published.scalar() or 0

    # Likes given
    res_likes = await db.execute(select(func.sum(FacebookPage.total_likes_given)))
    total_likes = res_likes.scalar() or 0

    # Check if any page has automation enabled
    res_active = await db.execute(
        select(func.count(FacebookPage.id)).where(FacebookPage.automation_enabled == True)
    )
    active_pages = res_active.scalar() or 0
    automation_active = active_pages > 0

    # Recent activity logs
    res_logs = await db.execute(
        select(ActionLog).order_by(ActionLog.created_at.desc()).limit(10)
    )
    recent_logs = res_logs.scalars().all()

    return {
        "total_pages_connected": total_pages,
        "total_posts_monitored": total_posts,
        "total_comments_received": total_comments,
        "pending_approvals_count": pending_count,
        "published_replies_count": published_count,
        "total_likes_given": total_likes,
        "automation_active": automation_active,
        "recent_activity": [ActionLogRead.model_validate(l) for l in recent_logs]
    }

@router.get("/logs", response_model=List[ActionLogRead])
async def list_action_logs(
    page_id: Optional[int] = Query(None),
    status: Optional[ActionStatus] = Query(None),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve audit action logs."""
    query = select(ActionLog).order_by(ActionLog.created_at.desc()).limit(limit)
    if page_id:
        query = query.where(ActionLog.page_id == page_id)
    if status:
        query = query.where(ActionLog.status == status)
    result = await db.execute(query)
    return result.scalars().all()

@router.post("/emergency-stop")
async def emergency_stop_all(db: AsyncSession = Depends(get_db)):
    """EMERGENCY KILL SWITCH: Immediately halts automation across all connected Facebook Pages."""
    await db.execute(
        update(FacebookPage).values(automation_enabled=False)
    )
    log = ActionLog(
        action_type="emergency_stop",
        status=ActionStatus.SUCCESS,
        details={"timestamp": datetime.now(timezone.utc).isoformat(), "message": "Global emergency stop triggered"}
    )
    db.add(log)
    await db.commit()
    return {"status": "success", "message": "All automations halted globally"}

@router.post("/resume-all")
async def resume_all_automations(db: AsyncSession = Depends(get_db)):
    """Resume automation across all connected Facebook Pages."""
    await db.execute(
        update(FacebookPage).values(automation_enabled=True)
    )
    log = ActionLog(
        action_type="global_resume",
        status=ActionStatus.SUCCESS,
        details={"timestamp": datetime.now(timezone.utc).isoformat(), "message": "Global automation resumed"}
    )
    db.add(log)
    await db.commit()
    return {"status": "success", "message": "All automations resumed"}
