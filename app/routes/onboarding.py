"""
Onboarding REST endpoints driven by the UI wizard.

  POST /onboarding/scrape    — fetch URL, run extraction, return preview profile
  POST /onboarding/confirm   — mark profile confirmed (after edits)
  POST /onboarding/agent     — save agent config (name + capabilities)
  GET  /onboarding/status    — current state for the user (gate the chat page)
  GET  /onboarding/profile   — full saved profile JSON
  GET  /onboarding/agent     — saved agent config

Every endpoint requires the caller's phone via the `Authorization: Bearer <jwt>`
header issued by /auth/verify.
"""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from app.routes.auth import verify_jwt
from app.services import agent_config, business_profile, openclaw_lock, ws_hub
from app.services.agent_config import DEFAULT_CAPABILITIES, AgentConfig
from app.services.business_profile import BrandKit, BusinessProfile
from app.services.onboarding import run_onboarding

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


def _phone_from_auth(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    return verify_jwt(token)


class ScrapeReq(BaseModel):
    url: str = Field(..., min_length=4)


class ConfirmReq(BaseModel):
    # Allow inline edits before saving — UI may have tweaked some fields.
    name: str | None = None
    type: str | None = None
    description: str | None = None
    address: str | None = None
    city: str | None = None
    contact_phone: str | None = None
    email: str | None = None
    timings: str | None = None
    services: list[str] | None = None
    tagline: str | None = None
    primary_color: str | None = None
    secondary_color: str | None = None
    accent_color: str | None = None
    tone: str | None = None
    visual_style: str | None = None


class AgentReq(BaseModel):
    name: str = Field(default="Morpheus", max_length=40)
    capabilities: list[str] = Field(default_factory=list)
    enabled_agents: list[str] = Field(default_factory=list)
    persona_extra: str = ""


@router.get("/capabilities")
async def list_capabilities() -> dict[str, Any]:
    return {"capabilities": DEFAULT_CAPABILITIES}


@router.get("/agents")
async def list_available_agents_route() -> dict[str, Any]:
    """All agents owners can enable. UI picker reads this."""
    return {"agents": agent_config.list_available_agents()}


@router.get("/status")
async def status(phone: str = Depends(_phone_from_auth)) -> dict[str, Any]:
    profile = business_profile.get(phone)
    cfg = agent_config.get(phone)
    return {
        "phone": phone,
        "has_profile": profile is not None,
        "profile_confirmed": bool(profile and profile.confirmed),
        "has_agent": cfg is not None,
        "step": _next_step(profile, cfg),
    }


def _next_step(profile: BusinessProfile | None, cfg: AgentConfig | None) -> str:
    if profile is None:
        return "scrape"
    if not profile.confirmed:
        return "confirm"
    if cfg is None:
        return "agent"
    return "ready"


@router.post("/scrape")
async def scrape(req: ScrapeReq, phone: str = Depends(_phone_from_auth)) -> dict[str, Any]:
    logger.info(f"onboarding scrape phone={phone} url={req.url}")
    ws_hub.fire(phone, channel="system", direction="out", kind="status",
                status="scraping", body=f"Scraping {req.url}")
    profile, summary = await run_onboarding(phone, req.url)
    ws_hub.fire(phone, channel="system", direction="out", kind="status",
                status="scrape_done")
    return {
        "summary": summary,
        "profile": profile.to_dict(),
        "next_step": _next_step(profile, agent_config.get(phone)),
    }


@router.post("/confirm")
async def confirm(req: ConfirmReq, phone: str = Depends(_phone_from_auth)) -> dict[str, Any]:
    profile = business_profile.get(phone)
    if profile is None:
        raise HTTPException(400, "no business profile to confirm — call /scrape first")

    # Apply edits from UI before locking.
    for field_ in ("name", "type", "description", "address", "city",
                   "contact_phone", "email", "timings"):
        v = getattr(req, field_, None)
        if v is not None:
            setattr(profile, field_, v.strip() or None)

    if req.services is not None:
        profile.services = [s.strip() for s in req.services if s and s.strip()][:8]

    brand_updates = {
        "tagline": req.tagline,
        "primary_color": req.primary_color,
        "secondary_color": req.secondary_color,
        "accent_color": req.accent_color,
        "tone": req.tone,
        "visual_style": req.visual_style,
    }
    for k, v in brand_updates.items():
        if v is not None:
            setattr(profile.brand, k, v.strip() or None)

    profile.confirmed = True
    business_profile.put(profile)
    logger.info(f"onboarding confirm phone={phone} business={profile.name!r}")
    ws_hub.fire(phone, channel="system", direction="out", kind="status",
                status="profile_confirmed")
    return {"ok": True, "profile": profile.to_dict(),
            "next_step": _next_step(profile, agent_config.get(phone))}


@router.post("/agent")
async def save_agent(req: AgentReq, phone: str = Depends(_phone_from_auth)) -> dict[str, Any]:
    profile = business_profile.get(phone)
    if profile is None or not profile.confirmed:
        raise HTTPException(400, "confirm business profile first")

    valid_caps = [c for c in req.capabilities if c in DEFAULT_CAPABILITIES]

    # Owner must pick at least one agent (or at least one legacy capability).
    if not req.enabled_agents and not valid_caps:
        raise HTTPException(400, "pick at least one agent or capability")

    cfg = AgentConfig(
        phone=phone,
        name=req.name.strip() or "Morpheus",
        capabilities=valid_caps,
        enabled_agents=req.enabled_agents,
        persona_extra=req.persona_extra.strip(),
    )
    # put() normalizes enabled_agents (drops unknown, infers from caps if empty)
    agent_config.put(cfg)
    saved = agent_config.get(phone)

    # Re-prime every enabled agent: scope/persona changed.
    openclaw_lock.clear_prime(phone)
    logger.info(
        f"onboarding agent saved phone={phone} name={cfg.name!r} "
        f"enabled_agents={saved.enabled_agents if saved else []}"
    )
    ws_hub.fire(phone, channel="system", direction="out", kind="status",
                status="agent_ready")
    # Fire-and-forget prime for every enabled agent. Each runs sequentially
    # inside prime_all_enabled to avoid hammering the OpenClaw VM proxy
    # session lock.
    asyncio.create_task(openclaw_lock.prime_all_enabled(phone))
    return {
        "ok": True,
        "agent": (saved.to_dict() if saved else cfg.to_dict()),
        "next_step": "ready",
    }


@router.get("/profile")
async def get_profile(phone: str = Depends(_phone_from_auth)) -> dict[str, Any]:
    profile = business_profile.get(phone)
    if profile is None:
        raise HTTPException(404, "no profile yet")
    return profile.to_dict()


@router.get("/agent")
async def get_agent(phone: str = Depends(_phone_from_auth)) -> dict[str, Any]:
    cfg = agent_config.get(phone)
    if cfg is None:
        raise HTTPException(404, "no agent config yet")
    return cfg.to_dict()


@router.post("/reset")
async def reset(phone: str = Depends(_phone_from_auth)) -> dict[str, Any]:
    """Clear profile + agent + prime flag so the user can redo onboarding."""
    openclaw_lock.reset(phone)
    logger.info(f"onboarding reset phone={phone}")
    return {"ok": True, "next_step": "scrape"}


@router.post("/reprime")
async def reprime(phone: str = Depends(_phone_from_auth)) -> dict[str, Any]:
    """
    Manually retry priming every enabled agent — useful if the OpenClaw
    VM was down at agent-save time and the fire-and-forget prime call
    failed for any agent.
    """
    openclaw_lock.clear_prime(phone)
    results = await openclaw_lock.prime_all_enabled(phone)
    return {
        "ok": all(results.values()) if results else False,
        "results": results,
    }
