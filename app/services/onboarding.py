"""
Onboarding orchestrator.

Two-LLM split (deliberate):
  - DATA EXTRACTION (URL → BusinessProfile JSON) goes via OpenRouter
    directly with strict JSON-schema response_format. Deterministic,
    cheap, fast, no persona drift.
  - AGENT REASONING (chat / multi-agent conversation) goes via OpenClaw.
    OpenClaw is the brain — it holds session memory, brand context,
    and the per-agent priming.

After extraction succeeds, the saved profile + agent config is shipped
to OpenClaw via `prime_all_enabled(phone)` so every enabled agent gets
the full business dossier in their primed session.
"""
from __future__ import annotations

from loguru import logger

from app.services import business_profile, llm_extract, scrape
from app.services.business_profile import BrandKit, BusinessProfile


# How much scraped text to ship to the extractor. 8k chars covers
# homepage + /about + /contact comfortably without burning tokens.
_MAX_SCRAPE_CHARS = 8000

# Our scrape.py enrichment markers. Stripped before extraction since the
# extractor reads visible text directly.
_NOISE_PREFIXES = ("[JSON-LD]", "[META]", "[VISIBLE TEXT]")


async def run_onboarding(phone: str, url: str) -> tuple[BusinessProfile, str]:
    """
    Execute the full onboarding for `phone` with the user-provided `url`.
    Returns (profile, summary_text). summary_text is what to send back
    to the user on WhatsApp.
    """
    pages = await scrape.fetch_with_aux(url)

    # combine text from all fetched pages, dedupe colors, keep first logo
    combined_text_parts: list[str] = []
    all_colors: list[str] = []
    seen_colors: set[str] = set()
    logo_url: str | None = None
    final_urls: list[str] = []

    for p in pages:
        if p.text:
            combined_text_parts.append(f"[{p.source} | {p.final_url}]\n{p.text}")
        for c in p.colors:
            if c not in seen_colors:
                seen_colors.add(c)
                all_colors.append(c)
        if not logo_url and p.logo_url:
            logo_url = p.logo_url
        if p.final_url:
            final_urls.append(p.final_url)

    combined_text = "\n\n".join(combined_text_parts)
    combined_text = _strip_scrape_noise(combined_text)[:_MAX_SCRAPE_CHARS]
    if not combined_text.strip():
        # nothing fetched — return a low-confidence profile so user sees the failure
        prof = BusinessProfile(phone=phone, source_urls=[url], confidence="low")
        business_profile.put(prof)
        return prof, (
            "I couldn't fetch any content from that link. "
            "Some sites block automated access (Instagram, Facebook). "
            "Try sharing your website URL or business Google Maps link."
        )

    parsed = await llm_extract.extract_profile(combined_text, all_colors)
    logger.info(
        f"onboarding extraction phone={phone} via=openrouter "
        f"keys={list(parsed.keys()) if parsed else 'EMPTY'}"
    )

    profile = _build_profile(
        phone=phone,
        url=url,
        parsed=parsed,
        colors=all_colors,
        logo_url=logo_url,
        source_urls=final_urls or [url],
    )
    business_profile.put(profile)

    summary = _format_summary(profile)
    return profile, summary


# ─── helpers ─────────────────────────────────────────────────────────────


def _strip_scrape_noise(text: str) -> str:
    """
    Drop our [JSON-LD] / [META] / [VISIBLE TEXT] tag lines before sending
    to the model. Helpful upstream signal during scraping but confuses
    smaller models that see structured tokens and try to mimic them.
    """
    lines = text.splitlines()
    out: list[str] = []
    skip_until_blank = False
    for line in lines:
        stripped = line.strip()
        if any(stripped.startswith(p) for p in _NOISE_PREFIXES):
            # Drop the marker. Following JSON-LD body until next blank stays
            # too because the marker absence triggers skip_until_blank.
            skip_until_blank = stripped.startswith("[JSON-LD]")
            continue
        if skip_until_blank:
            if not stripped:
                skip_until_blank = False
            continue
        out.append(line)
    cleaned = "\n".join(out).strip()
    # Also drop any standalone {...} JSON-looking lines longer than 80 chars —
    # these are JSON-LD remnants that survived the marker-removal pass.
    return cleaned


def _build_profile(
    *,
    phone: str,
    url: str,
    parsed: dict,
    colors: list[str],
    logo_url: str | None,
    source_urls: list[str],
) -> BusinessProfile:
    brand_raw = parsed.get("brand") or {}
    brand = BrandKit(
        primary_color=brand_raw.get("primary_color"),
        secondary_color=brand_raw.get("secondary_color"),
        accent_color=brand_raw.get("accent_color"),
        tone=brand_raw.get("tone"),
        visual_style=brand_raw.get("visual_style"),
        tagline=brand_raw.get("tagline"),
        logo_description=brand_raw.get("logo_description"),
    )

    socials = parsed.get("socials") or {}
    if not isinstance(socials, dict):
        socials = {}

    services = parsed.get("services") or []
    if not isinstance(services, list):
        services = []
    services = [str(s).strip() for s in services if str(s).strip()][:8]

    return BusinessProfile(
        phone=phone,
        name=_str_or_none(parsed.get("name")),
        type=_str_or_none(parsed.get("type")),
        category=_str_or_none(parsed.get("category")),
        description=_str_or_none(parsed.get("description")),
        address=_str_or_none(parsed.get("address")),
        city=_str_or_none(parsed.get("city")),
        contact_phone=_str_or_none(parsed.get("phone")),
        email=_str_or_none(parsed.get("email")),
        website=url,
        socials={k: str(v) for k, v in socials.items() if v},
        timings=_str_or_none(parsed.get("timings")),
        services=services,
        pricing_note=_str_or_none(parsed.get("pricing_note")),
        logo_url=logo_url,
        brand=brand,
        confidence=str(parsed.get("confidence") or "low").lower(),
        source_urls=source_urls,
        raw_colors=colors,
    )


def _str_or_none(v) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _format_summary(p: BusinessProfile) -> str:
    """Build a WhatsApp-friendly preview message asking for confirmation."""
    lines = ["📋 *Business profile preview*"]
    if p.name:
        lines.append(f"• Name: {p.name}")
    if p.type:
        type_line = p.type if not p.category else f"{p.type} ({p.category})"
        lines.append(f"• Type: {type_line}")
    if p.description:
        lines.append(f"• About: {p.description[:200]}")
    if p.city or p.address:
        loc = " — ".join(x for x in (p.city, p.address) if x)
        lines.append(f"• Location: {loc}")
    if p.contact_phone:
        lines.append(f"• Phone: {p.contact_phone}")
    if p.email:
        lines.append(f"• Email: {p.email}")
    if p.timings:
        lines.append(f"• Timings: {p.timings}")
    if p.services:
        lines.append(f"• Services: {', '.join(p.services[:5])}")
    if p.brand.tagline:
        lines.append(f"• Tagline: {p.brand.tagline}")
    if p.brand.primary_color or p.brand.secondary_color:
        cols = " ".join(
            c for c in (p.brand.primary_color, p.brand.secondary_color, p.brand.accent_color) if c
        )
        lines.append(f"• Brand colors: {cols}")
    if p.brand.tone or p.brand.visual_style:
        style = " / ".join(x for x in (p.brand.tone, p.brand.visual_style) if x)
        lines.append(f"• Style: {style}")
    if p.logo_url:
        lines.append(f"• Logo: {p.logo_url}")
    lines.append(f"• Confidence: {p.confidence}")
    lines.append("")
    lines.append("Reply *yes* to confirm or send another link to retry.")
    return "\n".join(lines)
