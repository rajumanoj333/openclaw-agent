"""
Per-phone OpenClaw session lock.

After onboarding, we 'prime' the OpenClaw session by sending a single
system-prompt turn that contains the full business context + agent
persona + scope. OpenClaw remembers the session via its own memory keyed
by `--to <phone>`. Subsequent chat turns ship only the bare user
message — no persona prefix, much smaller payloads.

Resetting clears the prime flag + business profile + agent config so
the user can redo onboarding with a different business.
"""
from __future__ import annotations

from threading import Lock

from loguru import logger


_PRIMED: dict[str, bool] = {}
_lock = Lock()


def is_primed(phone: str) -> bool:
    with _lock:
        return _PRIMED.get(phone, False)


def mark_primed(phone: str) -> None:
    with _lock:
        _PRIMED[phone] = True


def clear_prime(phone: str) -> None:
    with _lock:
        _PRIMED.pop(phone, None)


def reset(phone: str) -> None:
    """Wipe profile + agent + prime flag for a phone. UI 'reset' calls this."""
    from app.services import agent_config, business_profile

    clear_prime(phone)
    business_profile.delete(phone)
    agent_config.delete(phone)
    logger.info(f"openclaw_lock reset phone={phone}")


def build_system_prompt(phone: str) -> str:
    """Compose the locking system prompt from saved profile + agent cfg."""
    from app.services import agent_config, business_profile

    profile = business_profile.get(phone)
    cfg = agent_config.get(phone)
    if not profile or not cfg:
        return ""

    caps = ", ".join(c.replace("_", " ") for c in cfg.capabilities) or "general assistance"

    parts = [
        f"You are {cfg.name}, a marketing-focused AI employee for "
        f"{profile.name or 'the user'}.",
        "",
        "═══ BUSINESS CONTEXT ═══",
    ]
    if profile.name:
        parts.append(f"Name: {profile.name}")
    if profile.type:
        line = profile.type + (f" ({profile.category})" if profile.category else "")
        parts.append(f"Type: {line}")
    if profile.description:
        parts.append(f"About: {profile.description}")
    if profile.city or profile.address:
        loc = ", ".join(x for x in (profile.address, profile.city) if x)
        parts.append(f"Location: {loc}")
    if profile.timings:
        parts.append(f"Hours: {profile.timings}")
    if profile.services:
        parts.append(f"Services: {', '.join(profile.services)}")
    if profile.contact_phone:
        parts.append(f"Phone: {profile.contact_phone}")
    if profile.email:
        parts.append(f"Email: {profile.email}")
    if profile.website:
        parts.append(f"Website: {profile.website}")

    brand_lines: list[str] = []
    if profile.brand.tagline:
        brand_lines.append(f"Tagline: {profile.brand.tagline}")
    if profile.brand.tone:
        brand_lines.append(f"Tone: {profile.brand.tone}")
    if profile.brand.visual_style:
        brand_lines.append(f"Visual style: {profile.brand.visual_style}")
    colors = [
        c
        for c in (
            profile.brand.primary_color,
            profile.brand.secondary_color,
            profile.brand.accent_color,
        )
        if c
    ]
    if colors:
        brand_lines.append(f"Brand colors: {', '.join(colors)}")
    if profile.logo_url:
        brand_lines.append(f"Logo URL: {profile.logo_url}")

    if brand_lines:
        parts.append("")
        parts.append("═══ BRAND KIT ═══")
        parts.extend(brand_lines)

    parts.extend(
        [
            "",
            "═══ SCOPE ═══",
            f"You can ONLY handle: {caps}.",
            "If a user request falls outside this scope, politely decline and "
            "suggest the closest in-scope alternative.",
            "Always respect the brand colors, tone, and visual style above.",
        ]
    )

    if cfg.persona_extra.strip():
        parts.extend(
            ["", "═══ EXTRA INSTRUCTIONS ═══", cfg.persona_extra.strip()]
        )

    parts.extend(
        [
            "",
            "═══ ACK ═══",
            "Reply with one short sentence confirming you understand the brief. "
            "Do not list back the details. From the next turn on, treat user "
            "messages as live tasks.",
        ]
    )
    return "\n".join(parts)


async def prime(phone: str, *, timeout: int = 90) -> bool:
    """
    Send the system prompt to OpenClaw as a one-shot priming turn.
    Returns True on success, False on failure (caller may retry later).
    """
    if is_primed(phone):
        return True

    system = build_system_prompt(phone)
    if not system:
        logger.warning(f"openclaw_lock prime skipped — incomplete config phone={phone}")
        return False

    # local import — openclaw imports openclaw_lock, would be circular at module load
    from app.services.openclaw import ask_openclaw_raw

    try:
        await ask_openclaw_raw(system, to=phone, timeout=timeout)
        mark_primed(phone)
        logger.info(f"openclaw_lock primed phone={phone} chars={len(system)}")
        return True
    except Exception as e:
        logger.warning(f"openclaw_lock prime failed phone={phone}: {e!r}")
        return False
