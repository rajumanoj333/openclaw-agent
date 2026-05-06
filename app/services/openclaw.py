"""
OpenClaw client.

Two entry points:

  • ask_openclaw_raw(message, to=...) — ships the message verbatim, no wrapping.
    Used by the priming flow and by post-prime chat turns.

  • ask_openclaw(message, to=...) — smart sender. If the session is already
    primed (per `openclaw_lock`), ships bare message. Otherwise wraps with
    the legacy persona prefix so the agent still has context (graceful
    fallback when priming hasn't completed — e.g. VM was offline at
    onboarding time and never primed).
"""
from __future__ import annotations

import httpx
from loguru import logger

from app.config import settings


def _wrap_with_persona(message: str, phone: str | None) -> str:
    """
    Wrap a user message with the FULL system prompt (business profile +
    agent persona + scope + brand kit). Used for un-primed sessions so the
    agent always has complete context, even if priming hasn't run.
    """
    if not phone:
        return message
    try:
        from app.services.openclaw_lock import build_system_prompt
    except Exception:
        return message

    system = build_system_prompt(phone)
    if not system:
        return message
    return f"{system}\n\n--- USER MESSAGE ---\n{message}"


async def ask_openclaw_raw(
    message: str, *, to: str | None = None, timeout: int = 240
) -> str:
    """Ship `message` verbatim to OpenClaw. No wrapping, no prime checks."""
    url = f"{settings.openclaw_url.rstrip('/')}/agent"
    payload: dict = {"message": message, "agent": "main", "timeout": timeout}
    if to:
        payload["to"] = to

    async with httpx.AsyncClient(timeout=timeout + 30) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

    reply = (data.get("reply") or "").strip()
    logger.info(
        f"openclaw reply ms={data.get('ms')} session={data.get('session_id')} "
        f"chars_in={len(message)} chars_out={len(reply)}"
    )
    return reply or "(no reply)"


async def ask_openclaw(
    message: str, *, to: str | None = None, timeout: int = 240
) -> str:
    """
    Send `message` to OpenClaw. If the session for `to` is primed, ship the
    message bare; otherwise prepend the legacy persona prefix so context
    isn't lost while priming is pending.
    """
    if to:
        from app.services import openclaw_lock

        if openclaw_lock.is_primed(to):
            return await ask_openclaw_raw(message, to=to, timeout=timeout)

    wrapped = _wrap_with_persona(message, phone=to)
    return await ask_openclaw_raw(wrapped, to=to, timeout=timeout)
