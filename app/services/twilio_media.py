import httpx
from loguru import logger

from app.config import settings


async def download_media(url: str) -> tuple[bytes, str]:
    """
    Download a media file from a Twilio MediaUrl.

    Twilio media endpoints redirect to a signed S3 URL. The 1st request
    requires HTTP basic auth (Account SID + Auth Token); the redirect
    target does not. httpx follows redirects by default but strips the
    Authorization header on cross-origin hops, which is exactly what we
    need here.

    Returns (bytes, content_type).
    """
    auth = (settings.twilio_account_sid, settings.twilio_auth_token)
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        resp = await client.get(url, auth=auth)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "application/octet-stream")
        logger.info(
            f"twilio media downloaded bytes={len(resp.content)} type={content_type}"
        )
        return resp.content, content_type
