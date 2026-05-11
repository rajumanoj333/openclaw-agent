"""
Instagram publish endpoints. Auth was done manually in Composio dashboard,
so these only need the per-server Composio API key + entity_id from .env.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from app.routes.auth import verify_jwt
from app.services import instagram, ws_hub


router = APIRouter(prefix="/instagram", tags=["instagram"])


def auth_phone(authorization: str = Header(...)) -> str:
    """JWT bearer auth. verify_jwt() returns the phone string directly."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    phone = verify_jwt(token)  # raises HTTPException(401) on bad token
    if not phone:
        raise HTTPException(401, "invalid token")
    return phone


class PublishRequest(BaseModel):
    image_url: str = Field(..., min_length=1)
    caption: str = Field(default="", max_length=2200)


@router.get("/status")
async def status(phone: str = Depends(auth_phone)) -> dict[str, Any]:
    """Check Instagram connection — used by sidebar widget."""
    try:
        info = await instagram.get_account_info()
    except instagram.InstagramError as e:
        return {"connected": False, "error": str(e)}
    return {
        "connected": True,
        "username": info.get("username"),
        "name": info.get("name"),
        "followers_count": info.get("followers_count"),
        "media_count": info.get("media_count"),
        "ig_user_id": info.get("id"),
    }


@router.post("/publish")
async def publish(
    req: PublishRequest, phone: str = Depends(auth_phone)
) -> dict[str, Any]:
    """Publish a poster. Called by chat UI button next to media bubbles."""
    try:
        ws_hub.fire(
            phone, channel="system", direction="out", kind="status",
            status="instagram_publishing",
        )
        result = await instagram.publish_post(
            image_url=req.image_url, caption=req.caption
        )
    except instagram.InstagramError as e:
        logger.warning(f"instagram publish failed phone={phone}: {e!r}")
        ws_hub.fire(
            phone, channel="system", direction="out", kind="status",
            status="instagram_error", body=str(e),
        )
        raise HTTPException(502, str(e))

    ws_hub.fire(
        phone, channel="system", direction="out", kind="status",
        status="instagram_done", body=result.get("permalink"),
    )
    return result


@router.get("/recent")
async def recent(phone: str = Depends(auth_phone)) -> dict[str, Any]:
    """Last 12 posts for the connected account — sidebar grid."""
    try:
        items = await instagram.recent_posts(limit=12)
    except instagram.InstagramError as e:
        raise HTTPException(502, str(e))
    return {"items": items}
