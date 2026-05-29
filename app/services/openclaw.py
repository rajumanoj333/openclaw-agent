"""
OpenClaw client.

Two entry points:

  • ask_openclaw_raw(message, to=...) — ships the message verbatim, no
    wrapping. Used by the priming flow and post-prime chat turns. The
    `to` value is the OpenClaw --to key (uniquely identifies a session).

  • ask_openclaw(message, phone=..., agent_slug=...) — smart sender.
    Routes to the per-agent OpenClaw session (--to = phone:agent_slug).
    If that session is primed, ships the message bare. Otherwise wraps
    with the agent-specific system prompt so context isn't lost while
    priming is pending (graceful fallback when VM was offline at
    onboarding time).
"""
from __future__ import annotations

import httpx
from loguru import logger

from app.config import settings


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
        f"to={to} chars_in={len(message)} chars_out={len(reply)}"
    )
    return reply or "(no reply)"


async def ask_openclaw(
    message: str,
    *,
    phone: str | None = None,
    agent_slug: str = "morpheus",
    timeout: int = 240,
) -> str:
    """
    Smart sender keyed by (phone, agent_slug).

    - Determines OpenClaw session key: <phone>:<agent_slug>
    - If primed: ships bare message.
    - If not primed: wraps with that agent's full system prompt so the
      agent has business context immediately, even before priming runs.
    """
    from app.services import openclaw_lock
    from app.services.agents.registry import AGENT_REGISTRY

    # Validate slug; fall back to default if unknown
    if agent_slug not in AGENT_REGISTRY:
        logger.warning(f"unknown agent_slug={agent_slug}, falling back to morpheus")
        agent_slug = "morpheus"

    if not phone:
        # No phone → no session, no priming, just verbatim
        return await ask_openclaw_raw(message, to=None, timeout=timeout)

    session_key = openclaw_lock._session_key(phone, agent_slug)

    if openclaw_lock.is_primed(phone, agent_slug):
        return await ask_openclaw_raw(message, to=session_key, timeout=timeout)

    # Not primed — wrap with full system prompt for this (phone, agent)
    system = openclaw_lock.build_system_prompt(phone, agent_slug)
    if system:
        wrapped = f"{system}\n\n--- USER MESSAGE ---\n{message}"
        return await ask_openclaw_raw(wrapped, to=session_key, timeout=timeout)

    return await ask_openclaw_raw(message, to=session_key, timeout=timeout)
