"""System health status endpoint — used by UI's live indicator widget."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

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
