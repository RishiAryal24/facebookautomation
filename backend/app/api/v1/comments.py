from typing import List, Optional
from datetime import datetime, timezone
import random
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.entities import Comment, CommentStatus, Post, FacebookPage, ActionLog, ActionStatus
from app.schemas.schemas import (
    CommentRead, CommentApproveRequest, CommentRejectRequest,
    CommentRegenerateRequest, SimulateCommentRequest
)
from app.services.automation_runner import automation_engine
from app.services.gemini_service import gemini_service

router = APIRouter(prefix="/comments", tags=["Comments & Approval Queue"])

@router.get("/queue", response_model=List[CommentRead])
async def get_approval_queue(
    page_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve comments currently pending approval."""
    query = (
        select(Comment)
        .options(selectinload(Comment.post), selectinload(Comment.page))
        .where(Comment.status == CommentStatus.PENDING_APPROVAL)
        .order_by(Comment.created_at.desc())
    )
    if page_id:
        query = query.where(Comment.page_id == page_id)
    result = await db.execute(query)
    comments = result.scalars().all()
    
    # Map post message & page name for convenience
    output = []
    for c in comments:
        c_read = CommentRead.model_validate(c)
        c_read.post_message = c.post.message if c.post else None
        c_read.page_name = c.page.name if c.page else None
        output.append(c_read)
    return output

@router.get("/", response_model=List[CommentRead])
async def list_comments(
    status: Optional[CommentStatus] = Query(None),
    page_id: Optional[int] = Query(None),
    language: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """List all comments with filters."""
    query = (
        select(Comment)
        .options(selectinload(Comment.post), selectinload(Comment.page))
        .order_by(Comment.created_at.desc())
    )
    if status:
        query = query.where(Comment.status == status)
    if page_id:
        query = query.where(Comment.page_id == page_id)
    if language:
        query = query.where(Comment.detected_language == language)
        
    result = await db.execute(query)
    comments = result.scalars().all()
    
    output = []
    for c in comments:
        c_read = CommentRead.model_validate(c)
        c_read.post_message = c.post.message if c.post else None
        c_read.page_name = c.page.name if c.page else None
        output.append(c_read)
    return output

@router.post("/{comment_id}/approve", response_model=CommentRead)
async def approve_comment(
    comment_id: int,
    approve_data: CommentApproveRequest,
    db: AsyncSession = Depends(get_db)
):
    """Approve and publish an AI-generated comment to Facebook."""
    query = select(Comment).options(selectinload(Comment.page), selectinload(Comment.post)).where(Comment.id == comment_id)
    res = await db.execute(query)
    comment = res.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    success = await automation_engine.approve_and_publish_comment(
        db=db,
        comment=comment,
        edited_reply=approve_data.edited_reply,
        also_like=approve_data.also_like
    )

    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to publish comment: {comment.error_message}")

    c_read = CommentRead.model_validate(comment)
    c_read.page_name = comment.page.name
    c_read.post_message = comment.post.message
    return c_read

@router.post("/{comment_id}/reject", response_model=CommentRead)
async def reject_comment(
    comment_id: int,
    reject_data: CommentRejectRequest,
    db: AsyncSession = Depends(get_db)
):
    """Reject an AI draft."""
    query = select(Comment).options(selectinload(Comment.page), selectinload(Comment.post)).where(Comment.id == comment_id)
    res = await db.execute(query)
    comment = res.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    comment.status = CommentStatus.REJECTED
    comment.error_message = reject_data.reason or "Rejected by operator"
    
    log = ActionLog(
        page_id=comment.page_id,
        action_type="comment_rejected",
        status=ActionStatus.SUCCESS,
        details={"comment_id": comment.meta_comment_id, "reason": comment.error_message}
    )
    db.add(log)
    await db.commit()
    await db.refresh(comment)

    c_read = CommentRead.model_validate(comment)
    c_read.page_name = comment.page.name
    c_read.post_message = comment.post.message
    return c_read

@router.post("/{comment_id}/regenerate", response_model=CommentRead)
async def regenerate_comment(
    comment_id: int,
    regen_data: CommentRegenerateRequest,
    db: AsyncSession = Depends(get_db)
):
    """Regenerate draft using Gemini AI with alternative tone or language."""
    query = select(Comment).options(selectinload(Comment.page), selectinload(Comment.post)).where(Comment.id == comment_id)
    res = await db.execute(query)
    comment = res.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    tone = regen_data.tone or comment.page.response_tone or "friendly"
    target_lang = regen_data.target_language or comment.detected_language

    ai_result = await gemini_service.generate_comment_reply(
        comment_text=comment.message,
        post_context=comment.post.message if comment.post else "",
        brand_context=comment.page.brand_context if comment.page else "",
        tone=tone,
        target_language=target_lang,
        custom_instructions=regen_data.custom_instructions
    )

    comment.ai_draft_reply = ai_result.get("reply", comment.ai_draft_reply)
    if "detected_language" in ai_result:
        comment.detected_language = ai_result["detected_language"]
    if "sentiment" in ai_result:
        comment.sentiment = ai_result["sentiment"]

    await db.commit()
    await db.refresh(comment)

    c_read = CommentRead.model_validate(comment)
    c_read.page_name = comment.page.name
    c_read.post_message = comment.post.message
    return c_read

@router.post("/simulate", response_model=CommentRead)
async def simulate_incoming_comment(
    sim_data: SimulateCommentRequest,
    db: AsyncSession = Depends(get_db)
):
    """Simulate an incoming Facebook comment to test full automation / approval pipeline."""
    res_page = await db.execute(select(FacebookPage).where(FacebookPage.id == sim_data.page_id))
    page = res_page.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    # Get or find a post
    if sim_data.post_id:
        res_post = await db.execute(select(Post).where(Post.id == sim_data.post_id))
        post = res_post.scalar_one_or_none()
    else:
        res_post = await db.execute(select(Post).where(Post.page_id == page.id).order_by(Post.id.desc()))
        post = res_post.scalars().first()

    if not post:
        # Create a mock post if none exists
        post = Post(
            meta_post_id=f"sim_post_{int(datetime.now().timestamp())}",
            page_id=page.id,
            message="🌟 Welcome to PyLoom Official Facebook Page! We offer top quality digital products and nationwide delivery.",
            permalink_url="https://facebook.com/mock_post",
            is_monitored=True
        )
        db.add(post)
        await db.flush()

    unique_num = random.randint(10000, 99999)
    meta_comment_id = f"sim_cmt_{int(datetime.now().timestamp())}_{unique_num}"
    sender_id = f"user_{unique_num}"

    comment = await automation_engine.process_incoming_comment(
        db=db,
        page=page,
        post=post,
        sender_name=sim_data.sender_name,
        sender_id=sender_id,
        message=sim_data.message,
        meta_comment_id=meta_comment_id
    )

    c_read = CommentRead.model_validate(comment)
    c_read.page_name = page.name
    c_read.post_message = post.message
    return c_read
