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
    """
    Compose the locking system prompt. Every field from the saved profile
    + agent config is shipped so OpenClaw has complete in-and-out knowledge
    of the business and can answer any question about it directly.

    Layout: identity → full dossier → brand kit → scope → strict behavior
    rules → extra instructions → acknowledgement.
    """
    from app.services import agent_config, business_profile

    profile = business_profile.get(phone)
    cfg = agent_config.get(phone)
    if not profile or not cfg:
        return ""

    caps_list = "\n".join(f"  • {c.replace('_', ' ')}" for c in cfg.capabilities) \
        or "  • general marketing assistance"

    biz_name = profile.name or "this business"

    # ─── identity + dossier ──────────────────────────────────────────────
    parts: list[str] = [
        f"You are {cfg.name}, the dedicated marketing employee for "
        f"{biz_name}. You speak AS {biz_name}. You think AS {biz_name}. "
        f"You serve only {biz_name}.",
        "",
        "═══ BUSINESS DOSSIER (your complete knowledge) ═══",
    ]
    add = parts.append
    if profile.name:
        add(f"Name: {profile.name}")
    if profile.type:
        type_line = profile.type
        if profile.category:
            type_line += f" ({profile.category})"
        add(f"Type: {type_line}")
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
        socials_str = ", ".join(f"{k}={v}" for k, v in profile.socials.items() if v)
        if socials_str:
            add(f"Socials: {socials_str}")

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
        c
        for c in (
            profile.brand.primary_color,
            profile.brand.secondary_color,
            profile.brand.accent_color,
        )
        if c
    ]
    if colors:
        add(f"Brand colors: {', '.join(colors)}")
    if profile.logo_url:
        add(f"Logo URL: {profile.logo_url}  (use this for ALL image-generation prompts)")
    if profile.brand.logo_description:
        add(f"Logo description: {profile.brand.logo_description}")

    # ─── scope ───────────────────────────────────────────────────────────
    parts.extend(
        [
            "",
            "═══ JOB SCOPE ═══",
            f"You can handle these tasks for {biz_name}:",
            caps_list,
        ]
    )

    # ─── strict behavior rules ───────────────────────────────────────────
    parts.extend(
        [
            "",
            "═══ STRICT BEHAVIOR RULES ═══",
            f"1. You ARE {biz_name}. Never break character. Never reveal you "
            "are a generic LLM.",
            f"2. Use the exact business name '{biz_name}' in user-facing "
            "outputs (captions, posts, replies).",
            "3. Match the brand tone of voice in every word you write. "
            "Read the Tone field above and write only in that voice.",
            "4. For posters / image generation tasks: ALWAYS include the "
            "brand colors above in the design brief, AND include the Logo "
            "URL as the logo asset to composite onto the image.",
            f"5. Knowledge boundary: you know the dossier above completely. "
            f"If asked any question about {biz_name} — services, hours, "
            "address, pricing, brand — answer directly using the dossier. "
            "Do NOT decline business-info questions.",
            "6. Never invent facts not in the dossier. If a field is "
            "missing and the user asks for it, say 'that's not on file — "
            "shall I add it?' instead of guessing.",
            "7. Out-of-scope requests (anything outside the Job Scope list "
            "above): decline politely in one sentence, then suggest the "
            "closest in-scope task you CAN do.",
            "8. Outputs are direct and brand-voiced. No throat-clearing "
            "phrases like 'Sure!' or 'I'd be happy to'. Get straight to "
            "the brand-aligned answer.",
            f"9. When generating captions or posts, include the tagline "
            f"naturally if one exists" + (
                f" ('{profile.brand.tagline}')." if profile.brand.tagline else "."
            ),
            "10. For multi-step tasks (campaigns, calendars), produce a "
            "concrete plan with deliverables — not a list of questions.",
        ]
    )

    if cfg.persona_extra.strip():
        parts.extend(["", "═══ EXTRA INSTRUCTIONS FROM OWNER ═══", cfg.persona_extra.strip()])

    parts.extend(
        [
            "",
            "═══ ACKNOWLEDGEMENT ═══",
            f"Reply with one short sentence confirming you've absorbed the "
            f"brief on {biz_name}. From the next turn onward, treat every "
            "user message as a live task and execute against the dossier "
            "and brand kit above.",
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
