import json
import logging
import hmac

from fastapi import APIRouter, Request, Query, Response, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.core.database import get_db
from app.core.security import verify_meta_webhook_signature
from app.models.entities import Comment, FacebookPage, Post
from app.services.automation_runner import automation_engine

router = APIRouter(prefix="/webhook", tags=["Meta Webhooks"])
logger = logging.getLogger(__name__)

@router.get("/")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge")
):
    """Meta Webhook verification handshake."""
    if (
        hub_mode == "subscribe"
        and hub_verify_token
        and hmac.compare_digest(hub_verify_token, settings.META_VERIFY_TOKEN)
    ):
        return Response(content=hub_challenge, media_type="text/plain")
    return Response(content="Verification failed", status_code=status.HTTP_403_FORBIDDEN)

@router.post("/")
async def handle_webhook_event(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle incoming real-time Meta webhook notifications."""
    raw_payload = await request.body()
    if not settings.META_APP_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Meta webhook signature verification is not configured",
        )
    signature = request.headers.get("X-Hub-Signature-256")
    if not verify_meta_webhook_signature(raw_payload, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Meta webhook signature",
        )
    if settings.SIMULATION_MODE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Meta webhook processing is disabled in simulation mode",
        )
    try:
        payload = json.loads(raw_payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid webhook JSON body") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Webhook body must be a JSON object")
    
    if payload.get("object") != "page":
        return {"status": "ignored"}

    entries = payload.get("entry", [])
    if not isinstance(entries, list):
        raise HTTPException(status_code=400, detail="Webhook entry must be a list")
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        meta_page_id = entry.get("id")
        if not meta_page_id:
            continue
        # Check if page is registered
        res_page = await db.execute(
            select(FacebookPage).where(FacebookPage.meta_page_id == str(meta_page_id))
        )
        page = res_page.scalar_one_or_none()
        if not page or not page.automation_enabled:
            continue

        changes = entry.get("changes", [])
        if not isinstance(changes, list):
            continue
        for change in changes:
            if not isinstance(change, dict):
                continue
            val = change.get("value", {})
            if not isinstance(val, dict):
                continue
            item = val.get("item")
            verb = val.get("verb")

            # Handle new comments
            if item == "comment" and verb == "add":
                comment_id = val.get("comment_id")
                post_id_meta = val.get("post_id")
                sender = val.get("from", {})
                if not isinstance(sender, dict):
                    sender = {}
                sender_name = sender.get("name", "Facebook User")
                sender_id = sender.get("id")
                message = val.get("message", "")
                if not comment_id or not post_id_meta or not isinstance(message, str) or not message.strip():
                    logger.warning("Ignoring Meta comment event with missing required fields")
                    continue
                if sender_id and str(sender_id) == str(meta_page_id):
                    continue

                # Check or fetch post
                res_post = await db.execute(
                    select(Post).where(Post.meta_post_id == str(post_id_meta))
                )
                post = res_post.scalar_one_or_none()
                if post and post.page_id != page.id:
                    logger.warning("Ignoring Meta comment event whose post belongs to another Page")
                    continue
                if not post:
                    post = Post(
                        meta_post_id=str(post_id_meta),
                        page_id=page.id,
                        message="Facebook Post",
                        is_monitored=True
                    )
                    db.add(post)
                    await db.flush()

                # Process comment through automation pipeline
                try:
                    await automation_engine.process_incoming_comment(
                        db=db,
                        page=page,
                        post=post,
                        sender_name=sender_name if isinstance(sender_name, str) else "Facebook User",
                        sender_id=str(sender_id) if sender_id else "",
                        message=message.strip(),
                        meta_comment_id=str(comment_id),
                    )
                except IntegrityError:
                    await db.rollback()
                    existing = await db.execute(
                        select(Comment).where(Comment.meta_comment_id == str(comment_id))
                    )
                    if existing.scalar_one_or_none() is None:
                        raise

    return {"status": "processed"}
