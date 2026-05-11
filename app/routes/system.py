"""System status + public channel info — used by UI's live widget + login."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.config import settings
from app.services import system_health


router = APIRouter(prefix="/system", tags=["system"])


@router.get("/status")
async def status(phone: str | None = None) -> dict[str, Any]:
    """
    Aggregated health snapshot. Pass `?phone=+91...` to include per-phone
    probes like 'openclaw_primed'. No auth — health is non-sensitive.
    """
    services = await system_health.check_all(phone=phone)
    overall = (
        "down"
        if any(s["status"] == "down" for s in services)
        else "warn"
        if any(s["status"] == "warn" for s in services)
        else "ok"
    )
    return {"overall": overall, "services": services}


@router.get("/channels")
async def channels() -> dict[str, Any]:
    """
    Public-info endpoint: what numbers the user texts / calls to reach the
    agent. Returned to the login + chat sidebar so users know the inbound
    contacts. No auth — these are advertised Twilio numbers.
    """
    # Strip Twilio's `whatsapp:` prefix for display, keep the E.164 number.
    wa = (settings.twilio_whatsapp_from or "").replace("whatsapp:", "").strip()
    voice = (settings.twilio_voice_from or "").strip()
    return {
        "whatsapp": wa or None,
        "voice": voice or None,
        "demo_mode": settings.app_env == "dev",
    }
