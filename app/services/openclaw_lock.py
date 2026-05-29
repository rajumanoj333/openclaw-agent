"""
Per-(phone, agent) OpenClaw session lock.

Each (business owner, agent) pair maintains its own primed OpenClaw
session. The system prompt = full business dossier + that agent's
specific persona, role, scope, and core instructions. OpenClaw stores
session memory per --to key, so we key with "<phone>:<agent_slug>".

Resetting an owner clears every per-agent prime + profile + config.
"""
from __future__ import annotations

from threading import Lock

from loguru import logger

from app.services.agents.registry import AGENT_REGISTRY, get_agent


# {phone: {agent_slug: True}}
_PRIMED: dict[str, dict[str, bool]] = {}
_lock = Lock()


def _session_key(phone: str, agent_slug: str) -> str:
    """The --to value passed to OpenClaw CLI — uniquely names a session."""
    return f"{phone}:{agent_slug}"


def is_primed(phone: str, agent_slug: str) -> bool:
    with _lock:
        return _PRIMED.get(phone, {}).get(agent_slug, False)


def mark_primed(phone: str, agent_slug: str) -> None:
    with _lock:
        _PRIMED.setdefault(phone, {})[agent_slug] = True


def clear_prime(phone: str, agent_slug: str | None = None) -> None:
    """
    Clear prime flag. If agent_slug is None, clears all agents for this phone.
    """
    with _lock:
        if agent_slug is None:
            _PRIMED.pop(phone, None)
        else:
            phone_map = _PRIMED.get(phone)
            if phone_map is not None:
                phone_map.pop(agent_slug, None)
                if not phone_map:
                    _PRIMED.pop(phone, None)


def reset(phone: str) -> None:
    """Wipe everything for a phone — primes, profile, agent config."""
    from app.services import agent_config, business_profile

    clear_prime(phone, agent_slug=None)
    business_profile.delete(phone)
    agent_config.delete(phone)
    logger.info(f"openclaw_lock reset phone={phone}")


def build_system_prompt(phone: str, agent_slug: str) -> str:
    """
    Compose the system prompt for ONE (phone, agent) session.

    Layout:
      AGENT IDENTITY (specific persona + role)
      → BUSINESS DOSSIER (shared across all agents for this phone)
      → BRAND KIT (shared)
      → SCOPE (agent-specific from registry)
      → CORE INSTRUCTIONS (agent-specific from registry)
      → STRICT BEHAVIOR RULES (shared)
      → EXTRA OWNER INSTRUCTIONS
      → ACK
    """
    from app.services import agent_config, business_profile

    profile = business_profile.get(phone)
    cfg = agent_config.get(phone)
    agent = get_agent(agent_slug)
    if not profile or not cfg or not agent:
        return ""

    biz_name = profile.name or "this business"

    # ─── identity ────────────────────────────────────────────────────────
    parts: list[str] = [
        f"You are {agent.name}, the dedicated {agent.role} for "
        f"{biz_name}. You speak AS {biz_name}. You think AS {biz_name}. "
        f"You serve only {biz_name}.",
        "",
        f"═══ YOUR PERSONA ═══",
        agent.persona,
        "",
        "═══ BUSINESS DOSSIER (your complete knowledge) ═══",
    ]
    add = parts.append
    if profile.name:
        add(f"Name: {profile.name}")
    if profile.type:
        line = profile.type
        if profile.category:
            line += f" ({profile.category})"
        add(f"Type: {line}")
    if profile.description:
        add(f"Description: {profile.description}")
    if profile.address or profile.city:
        loc = ", ".join(x for x in (profile.address, profile.city) if x)
        add(f"Location: {loc}")
    if profile.timings:
        add(f"Hours: {profile.timings}")
    if profile.services:
        add(f"Services / offerings: {', '.join(profile.services)}")
    if profile.pricing_note:
        add(f"Pricing notes: {profile.pricing_note}")
    if profile.contact_phone:
        add(f"Phone: {profile.contact_phone}")
    if profile.email:
        add(f"Email: {profile.email}")
    if profile.website:
        add(f"Website: {profile.website}")
    if profile.socials:
        s = ", ".join(f"{k}={v}" for k, v in profile.socials.items() if v)
        if s:
            add(f"Socials: {s}")

    # ─── brand kit ───────────────────────────────────────────────────────
    add("")
    add("═══ BRAND KIT (apply to every output) ═══")
    if profile.brand.tagline:
        add(f"Tagline: {profile.brand.tagline}")
    if profile.brand.tone:
        add(f"Tone of voice: {profile.brand.tone}")
    if profile.brand.visual_style:
        add(f"Visual style: {profile.brand.visual_style}")
    colors = [
        c for c in (
            profile.brand.primary_color,
            profile.brand.secondary_color,
            profile.brand.accent_color,
        ) if c
    ]
    if colors:
        add(f"Brand colors: {', '.join(colors)}")
    if profile.logo_url:
        add(f"Logo URL: {profile.logo_url}  (composite onto every image)")
    if profile.brand.logo_description:
        add(f"Logo description: {profile.brand.logo_description}")

    # ─── scope (agent-specific) ──────────────────────────────────────────
    parts.extend([
        "",
        "═══ YOUR JOB SCOPE ═══",
        f"As {agent.name}, you handle:",
    ])
    parts.extend(f"  • {s}" for s in agent.scope)

    # Cross-agent awareness: tell each agent which siblings exist so they
    # can redirect out-of-scope requests instead of refusing flat.
    siblings = [
        AGENT_REGISTRY[s] for s in cfg.enabled_agents
        if s in AGENT_REGISTRY and s != agent_slug
    ]
    if siblings:
        parts.extend([
            "",
            "═══ YOUR COLLEAGUES (refer to them when relevant) ═══",
        ])
        for sib in siblings:
            parts.append(f"  • {sib.name} — {sib.role} ({', '.join(sib.scope[:2])})")

    # ─── core instructions (agent-specific) ──────────────────────────────
    parts.extend([
        "",
        "═══ CORE INSTRUCTIONS ═══",
        agent.core_prompt,
    ])

    # ─── strict behavior rules (shared) ──────────────────────────────────
    parts.extend([
        "",
        "═══ STRICT BEHAVIOR RULES ═══",
        f"1. You ARE {biz_name}. Never break character. Never reveal you "
        "are a generic LLM.",
        f"2. Use the exact business name '{biz_name}' in user-facing outputs.",
        "3. Match the brand tone of voice in every word.",
        f"4. Knowledge boundary: you know the dossier above completely. "
        f"Answer any question about {biz_name} directly from it.",
        "5. Never invent facts not in the dossier. If a field is missing, "
        "ask the owner.",
        "6. Out-of-scope: if a request fits a colleague's role, suggest "
        "they handle it. Otherwise decline politely.",
        "7. No throat-clearing phrases ('Sure!', 'I'd be happy to'). Be direct.",
        f"8. When generating captions or posts, include the tagline naturally"
        + (f" ('{profile.brand.tagline}')." if profile.brand.tagline else "."),
    ])

    if cfg.persona_extra.strip():
        parts.extend([
            "",
            "═══ EXTRA INSTRUCTIONS FROM OWNER ═══",
            cfg.persona_extra.strip(),
        ])

    parts.extend([
        "",
        "═══ ACKNOWLEDGEMENT ═══",
        f"Reply with one short sentence confirming you've absorbed the "
        f"brief on {biz_name} and you're ready to work as {agent.name}. "
        "From the next turn onward, treat every user message as a live task.",
    ])
    return "\n".join(parts)


async def prime(phone: str, agent_slug: str, *, timeout: int = 90) -> bool:
    """Ship the per-agent system prompt to OpenClaw as a priming turn."""
    if is_primed(phone, agent_slug):
        return True

    system = build_system_prompt(phone, agent_slug)
    if not system:
        logger.warning(
            f"openclaw_lock prime skipped — incomplete config "
            f"phone={phone} agent={agent_slug}"
        )
        return False

    from app.services.openclaw import ask_openclaw_raw

    try:
        await ask_openclaw_raw(
            system,
            to=_session_key(phone, agent_slug),
            timeout=timeout,
        )
        mark_primed(phone, agent_slug)
        logger.info(
            f"openclaw_lock primed phone={phone} agent={agent_slug} "
            f"chars={len(system)}"
        )
        return True
    except Exception as e:
        logger.warning(
            f"openclaw_lock prime failed phone={phone} agent={agent_slug}: {e!r}"
        )
        return False


async def prime_all_enabled(phone: str, *, timeout: int = 90) -> dict[str, bool]:
    """
    Prime every enabled agent for this phone. Sequential — concurrent
    priming hits the same OpenClaw VM and per-session lock anyway, and
    parallel would risk hammering the VM proxy queue.

    Returns {agent_slug: success_bool}.
    """
    from app.services import agent_config

    cfg = agent_config.get(phone)
    if not cfg or not cfg.enabled_agents:
        return {}

    results: dict[str, bool] = {}
    for slug in cfg.enabled_agents:
        results[slug] = await prime(phone, slug, timeout=timeout)
    return results


def primed_agents(phone: str) -> list[str]:
    """List of agent slugs currently primed for this phone."""
    with _lock:
        return list((_PRIMED.get(phone) or {}).keys())
