"""
Aggregated health probes for every external dep the agent talks to.

Used by the UI's system-status widget. All probes run in parallel via
asyncio.gather, each capped at a short timeout, so total widget latency
equals the slowest single probe (~2s typical), not the sum.

Each probe returns ServiceStatus with:
  status: 'ok' | 'warn' | 'down'
  latency_ms: int
  detail:    short human-readable note (one-line)
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import asdict, dataclass
from typing import Any, Awaitable, Callable

import httpx
from loguru import logger

from app.config import settings


@dataclass
class ServiceStatus:
    name: str
    status: str  # 'ok' | 'warn' | 'down'
    latency_ms: int = 0
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


async def _timed(coro: Awaitable[tuple[str, str]]) -> tuple[str, str, int]:
    """Run an async probe and return (status, detail, latency_ms)."""
    t0 = time.time()
    try:
        status, detail = await coro
    except asyncio.TimeoutError:
        return "down", "timeout", int((time.time() - t0) * 1000)
    except Exception as e:
        return "down", f"{type(e).__name__}: {e}"[:160], int(
            (time.time() - t0) * 1000
        )
    return status, detail, int((time.time() - t0) * 1000)


# ─── individual probes ───────────────────────────────────────────────────


async def _probe_fastapi() -> tuple[str, str]:
    return "ok", "process alive"


async def _probe_openclaw_proxy() -> tuple[str, str]:
    """SSH-tunnelled VM proxy on settings.openclaw_url."""
    base = settings.openclaw_url.rstrip("/")
    async with httpx.AsyncClient(timeout=3.0) as client:
        r = await client.get(f"{base}/health")
    if r.status_code != 200:
        return "down", f"HTTP {r.status_code}"
    return "ok", "proxy reachable"


async def _probe_ngrok() -> tuple[str, str]:
    """Local ngrok admin API on 4040 (only works if ngrok runs on laptop)."""
    async with httpx.AsyncClient(timeout=2.0) as client:
        r = await client.get("http://127.0.0.1:4040/api/tunnels")
    if r.status_code != 200:
        return "down", f"admin HTTP {r.status_code}"
    data = r.json()
    tunnels = data.get("tunnels") or []
    if not tunnels:
        return "warn", "ngrok running but no tunnels"
    pub = tunnels[0].get("public_url", "")
    return "ok", pub.replace("https://", "")[:48]


async def _probe_twilio() -> tuple[str, str]:
    """Check Twilio creds exist + Account API responds."""
    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        return "down", "creds missing in .env"
    url = (
        f"https://api.twilio.com/2010-04-01/Accounts/"
        f"{settings.twilio_account_sid}.json"
    )
    auth = (settings.twilio_account_sid, settings.twilio_auth_token)
    async with httpx.AsyncClient(timeout=3.0, auth=auth) as client:
        r = await client.get(url)
    if r.status_code == 401:
        return "down", "401 — bad credentials"
    if r.status_code != 200:
        return "warn", f"HTTP {r.status_code}"
    status = r.json().get("status", "active")
    return "ok", f"account {status}"


async def _probe_gemini() -> tuple[str, str]:
    """Gemini key present + model list reachable."""
    key = settings.gemini_key
    if not key:
        return "down", "GEMINI_API_KEY missing"
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
        "&pageSize=1"
    )
    async with httpx.AsyncClient(timeout=4.0) as client:
        r = await client.get(url)
    if r.status_code == 401 or r.status_code == 403:
        return "down", f"{r.status_code} — bad key"
    if r.status_code != 200:
        return "warn", f"HTTP {r.status_code}"
    return "ok", "API reachable"


async def _probe_pollinations() -> tuple[str, str]:
    """Free image gen service — HEAD on root."""
    async with httpx.AsyncClient(timeout=3.0, follow_redirects=True) as client:
        r = await client.head("https://image.pollinations.ai/")
    if r.status_code >= 500:
        return "warn", f"HTTP {r.status_code} (often transient)"
    if r.status_code >= 400:
        return "down", f"HTTP {r.status_code}"
    return "ok", "service reachable"


async def _probe_sarvam() -> tuple[str, str]:
    """Sarvam STT/TTS root probe — auth not required for health-ish endpoint."""
    key = settings.sarvam_key
    if not key:
        return "warn", "SARVAM_API_KEY missing (voice will use fallback)"
    base = settings.sarvam_base_url.rstrip("/")
    async with httpx.AsyncClient(timeout=3.0) as client:
        r = await client.get(base)
    # Sarvam root returns 200 or 404 (depending on version) — both are alive
    if r.status_code >= 500:
        return "down", f"HTTP {r.status_code}"
    return "ok", "API reachable"


async def _probe_composio() -> tuple[str, str]:
    """Composio + Instagram connection via existing /instagram/status helper."""
    if not settings.composio_api_key:
        return "down", "COMPOSIO_API_KEY missing"
    # Reuse the well-tested helper from instagram service
    from app.services import instagram

    try:
        info = await instagram.get_account_info()
    except instagram.InstagramError as e:
        return "down", str(e)[:160]
    username = info.get("username") or "unknown"
    return "ok", f"@{username}"


async def _probe_openclaw_lock(phone: str | None) -> tuple[str, str]:
    """Whether OpenClaw session is primed for this phone (post-onboarding)."""
    if not phone:
        return "warn", "no phone (not signed in)"
    from app.services import openclaw_lock

    if openclaw_lock.is_primed(phone):
        return "ok", "primed for current biz"
    return "warn", "not primed yet"


# ─── aggregator ──────────────────────────────────────────────────────────


_PROBES: dict[str, Callable[[], Awaitable[tuple[str, str]]]] = {
    "fastapi":         _probe_fastapi,
    "ngrok":           _probe_ngrok,
    "openclaw_proxy":  _probe_openclaw_proxy,
    "twilio":          _probe_twilio,
    "gemini":          _probe_gemini,
    "pollinations":    _probe_pollinations,
    "sarvam":          _probe_sarvam,
    "composio":        _probe_composio,
}


async def check_all(phone: str | None = None) -> list[dict[str, Any]]:
    """Run every probe in parallel. Per-phone probes (e.g. prime) tacked on."""
    names = list(_PROBES.keys())
    coros = [_timed(_PROBES[n]()) for n in names]
    # Per-phone probe (needs phone arg)
    names.append("openclaw_primed")
    coros.append(_timed(_probe_openclaw_lock(phone)))

    results = await asyncio.gather(*coros, return_exceptions=False)

    out: list[ServiceStatus] = []
    for name, (status, detail, ms) in zip(names, results):
        out.append(ServiceStatus(name=name, status=status, latency_ms=ms, detail=detail))
    logger.debug(
        "system_health snapshot: " + ", ".join(
            f"{s.name}={s.status}({s.latency_ms}ms)" for s in out
        )
    )
    return [s.to_dict() for s in out]
