"""
Instagram publish flow via Composio (REST, v3 API).

Auth was completed manually in the Composio dashboard, so we just need the
API key + entity_id. Composio holds the OAuth tokens and signs Graph API
calls on our behalf.

Three steps for a publish:
  1. INSTAGRAM_POST_IG_USER_MEDIA — create container with image_url + caption
  2. INSTAGRAM_GET_IG_MEDIA — poll status until status_code='FINISHED'
  3. INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH — publish the container

Image URL must be a direct public HTTPS link to JPG/PNG (320–1440px wide,
≤8MB, aspect 4:5–1.91:1). We serve composited posters via the existing
/audio/{name}.jpg route through the ngrok tunnel for public access.
"""
from __future__ import annotations

import asyncio
import io
import time
from typing import Any

import httpx
from loguru import logger

from app.config import settings


_COMPOSIO_BASE = "https://backend.composio.dev"

# Meta requires aspect ratio between 4:5 (0.8) and 1.91:1 for feed posts.
# Posters here are generated 9:16 (~0.56) which fails. Center-crop to 4:5
# before publishing.
_IG_TARGET_ASPECT = 4 / 5  # 0.8 — Meta's narrowest feed-supported ratio

# Cached Instagram Business Account ID — fetched once via GET_USER_INFO and
# reused for subsequent publishes. Avoids the user having to paste the
# numeric ID into env.
_ig_user_id_cache: dict[str, str] = {}


class InstagramError(RuntimeError):
    """Wraps any Composio / Graph API failure with a readable message."""


async def _execute(action: str, params: dict[str, Any]) -> dict[str, Any]:
    """
    Run a Composio action via v3 tools/execute. Falls back to v2
    actions/{slug}/execute on 404 (older accounts may still be on v2).
    """
    api_key = settings.composio_api_key.strip()
    if not api_key:
        raise InstagramError("COMPOSIO_API_KEY missing in .env")

    user_id = settings.composio_user_id.strip() or "default"
    headers = {"x-api-key": api_key, "Content-Type": "application/json"}

    # v3 first
    v3_url = f"{_COMPOSIO_BASE}/api/v3/tools/execute"
    v3_body = {"toolSlug": action, "userId": user_id, "arguments": params}
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            r = await client.post(v3_url, json=v3_body, headers=headers)
            if r.status_code == 200:
                return r.json()
            if r.status_code != 404:
                raise InstagramError(
                    f"Composio v3 {action} {r.status_code}: {r.text[:300]}"
                )
        except httpx.HTTPError as e:
            logger.warning(f"composio v3 transport error: {e!r} — trying v2")

        # v2 fallback
        v2_url = f"{_COMPOSIO_BASE}/api/v2/actions/{action}/execute"
        v2_body = {"input": params, "entityId": user_id}
        r = await client.post(v2_url, json=v2_body, headers=headers)
        if r.status_code != 200:
            raise InstagramError(
                f"Composio v2 {action} {r.status_code}: {r.text[:300]}"
            )
        return r.json()


def _unwrap_data(envelope: dict[str, Any]) -> dict[str, Any]:
    """
    Composio wraps tool output in different shapes across v2/v3:
      v3: {"data": {...}, "successful": bool, "error": str}
      v2: {"response_data": {...}, "successful": bool}
      sometimes:  {"data": {"data": {...}}}  (Graph API echo)
    Normalize to the inner data dict.
    """
    if not envelope.get("successful", True) and envelope.get("error"):
        raise InstagramError(str(envelope["error"]))
    data = envelope.get("data") or envelope.get("response_data") or {}
    if isinstance(data, dict) and isinstance(data.get("data"), dict):
        # Some Graph API echoes nest one more level
        return data["data"]
    return data if isinstance(data, dict) else {}


async def get_account_info() -> dict[str, Any]:
    """
    Returns Instagram Business Account info (username, name, followers).
    Side-effect: caches numeric IG User ID for later publish calls.
    """
    envelope = await _execute("INSTAGRAM_GET_USER_INFO", {"ig_user_id": "me"})
    data = _unwrap_data(envelope)
    ig_id = str(data.get("id") or "")
    if ig_id:
        _ig_user_id_cache["me"] = ig_id
    return data


async def _ig_user_id() -> str:
    """Cached Instagram Business Account numeric ID."""
    cached = _ig_user_id_cache.get("me")
    if cached:
        return cached
    info = await get_account_info()
    ig_id = str(info.get("id") or "")
    if not ig_id:
        raise InstagramError("Could not resolve Instagram Business Account ID")
    return ig_id


async def _crop_to_ig_aspect(source_url: str) -> str:
    """
    Fetch poster from `source_url`, center-crop to 4:5 if it's taller, save
    a new copy to audio_store, and return its public URL. Meta rejects
    images outside 4:5–1.91:1 aspect range, and our posters are 9:16.

    If the image already meets Meta's requirements, returns the original URL
    unchanged (no I/O wasted).
    """
    # Lazy imports — keep instagram module light at boot
    from PIL import Image
    from app.services.audio_store import save as save_audio

    base = settings.public_base_url.rstrip("/")
    if not base:
        raise InstagramError(
            "PUBLIC_BASE_URL not set — cannot host cropped image for Meta"
        )

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        r = await client.get(source_url)
        r.raise_for_status()
        raw = r.content

    def _crop() -> bytes:
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        w, h = img.size
        aspect = w / h
        # Already wide enough? Skip crop.
        if aspect >= _IG_TARGET_ASPECT:
            out = io.BytesIO()
            img.save(out, format="JPEG", quality=92, optimize=True)
            return out.getvalue()
        # Taller than 4:5 → crop height. New height = width / 0.8 = width * 1.25
        new_h = int(w / _IG_TARGET_ASPECT)
        top = max(0, (h - new_h) // 2)
        cropped = img.crop((0, top, w, top + new_h))
        out = io.BytesIO()
        cropped.save(out, format="JPEG", quality=92, optimize=True)
        return out.getvalue()

    jpeg = await asyncio.to_thread(_crop)
    name = save_audio(jpeg, "jpg")  # auto-uuid filename, returns name
    public_url = f"{base}/audio/{name}"
    logger.info(
        f"instagram crop saved name={name} bytes={len(jpeg)} url={public_url}"
    )
    return public_url


async def publish_post(*, image_url: str, caption: str) -> dict[str, Any]:
    """
    Full create → poll → publish flow. Returns {post_id, permalink, ms}.
    Raises InstagramError with detail on any failure step.
    """
    if not image_url.startswith("https://"):
        raise InstagramError(
            "image_url must be a direct public HTTPS URL — Meta does not "
            "fetch http://, data: URIs, /api/img proxies, or relative paths."
        )
    lower = image_url.lower()
    if any(host in lower for host in ("localhost", "127.0.0.1", "0.0.0.0")):
        raise InstagramError(
            f"image_url is not publicly reachable: {image_url}. Expose via "
            "ngrok / cloud host first."
        )
    if "/api/img?" in image_url:
        raise InstagramError(
            "image_url points at the UI /api/img proxy. Pass the upstream "
            "image URL directly instead."
        )

    t0 = time.time()
    ig_id = await _ig_user_id()

    # 0. Crop to IG-compliant aspect (4:5 minimum). Posters are 9:16 source.
    try:
        publish_url = await _crop_to_ig_aspect(image_url)
    except InstagramError:
        raise
    except Exception as e:
        # Crop failed (network, Pillow, audio_store) → try original anyway,
        # Meta might accept if it's already wide enough.
        logger.warning(f"ig crop failed: {e!r} — using original url")
        publish_url = image_url

    # 1. create container
    container_env = await _execute(
        "INSTAGRAM_POST_IG_USER_MEDIA",
        {
            "ig_user_id": ig_id,
            "image_url": publish_url,
            "caption": caption[:2200],  # Instagram caption cap
        },
    )
    container = _unwrap_data(container_env)
    creation_id = str(container.get("id") or container.get("creation_id") or "")
    if not creation_id:
        raise InstagramError(
            f"container creation returned no id: {container}"
        )
    logger.info(f"instagram container created id={creation_id}")

    # 2. poll status
    for attempt in range(20):
        await asyncio.sleep(3)
        status_env = await _execute(
            "INSTAGRAM_GET_IG_MEDIA",
            {"ig_media_id": creation_id, "fields": "status_code"},
        )
        status_data = _unwrap_data(status_env)
        code = str(status_data.get("status_code") or "").upper()
        if code == "FINISHED":
            break
        if code == "ERROR":
            raise InstagramError(
                f"container processing failed: {status_data}"
            )
        logger.debug(f"instagram poll {attempt+1} status={code or 'pending'}")
    else:
        raise InstagramError(
            f"container {creation_id} did not reach FINISHED within 60s"
        )

    # 3. publish
    publish_env = await _execute(
        "INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH",
        {"ig_user_id": ig_id, "creation_id": creation_id},
    )
    published = _unwrap_data(publish_env)
    post_id = str(published.get("id") or "")
    if not post_id:
        raise InstagramError(f"publish returned no id: {published}")

    # Fetch permalink for the live URL
    permalink: str | None = None
    try:
        media_env = await _execute(
            "INSTAGRAM_GET_IG_MEDIA",
            {"ig_media_id": post_id, "fields": "permalink"},
        )
        permalink = _unwrap_data(media_env).get("permalink")
    except Exception as e:
        logger.warning(f"failed to fetch permalink for {post_id}: {e!r}")

    ms = int((time.time() - t0) * 1000)
    logger.info(f"instagram post published id={post_id} ms={ms} permalink={permalink}")
    return {"post_id": post_id, "permalink": permalink, "ms": ms}


async def recent_posts(limit: int = 12) -> list[dict[str, Any]]:
    """Recent media for the connected account — sidebar grid."""
    ig_id = await _ig_user_id()
    env = await _execute(
        "INSTAGRAM_GET_IG_USER_MEDIA",
        {
            "ig_user_id": ig_id,
            "limit": limit,
            "fields": "id,caption,media_type,media_url,permalink,timestamp,like_count",
        },
    )
    data = _unwrap_data(env)
    items = data.get("data") if isinstance(data, dict) else None
    return items if isinstance(items, list) else []
