from fastapi import APIRouter, Request, Query, Response, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.core.database import get_db
from app.models.entities import FacebookPage, Post
from app.services.automation_runner import automation_engine

router = APIRouter(prefix="/webhook", tags=["Meta Webhooks"])

@router.get("/")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge")
):
    """Meta Webhook verification handshake."""
    if hub_mode == "subscribe" and hub_verify_token == settings.META_VERIFY_TOKEN:
        return Response(content=hub_challenge, media_type="text/plain")
    return Response(content="Verification failed", status_code=status.HTTP_403_FORBIDDEN)

@router.post("/")
async def handle_webhook_event(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle incoming real-time Meta webhook notifications."""
    payload = await request.json()
    
    if payload.get("object") != "page":
        return {"status": "ignored"}

    for entry in payload.get("entry", []):
        meta_page_id = entry.get("id")
        # Check if page is registered
        res_page = await db.execute(select(FacebookPage).where(FacebookPage.meta_page_id == meta_page_id))
        page = res_page.scalar_one_or_none()
        if not page or not page.automation_enabled:
            continue

        for change in entry.get("changes", []):
            val = change.get("value", {})
            item = val.get("item")
            verb = val.get("verb")

            # Handle new comments
            if item == "comment" and verb == "add":
                comment_id = val.get("comment_id")
                post_id_meta = val.get("post_id")
                sender_name = val.get("from", {}).get("name", "Facebook User")
                sender_id = val.get("from", {}).get("id")
                message = val.get("message", "")

                # Check or fetch post
                res_post = await db.execute(select(Post).where(Post.meta_post_id == post_id_meta))
                post = res_post.scalar_one_or_none()
                if not post:
                    post = Post(
                        meta_post_id=post_id_meta,
                        page_id=page.id,
                        message="Facebook Post",
                        is_monitored=True
                    )
                    db.add(post)
                    await db.flush()

                # Process comment through automation pipeline
                await automation_engine.process_incoming_comment(
                    db=db,
                    page=page,
                    post=post,
                    sender_name=sender_name,
                    sender_id=sender_id,
                    message=message,
                    meta_comment_id=comment_id
                )

    return {"status": "processed"}
