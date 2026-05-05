"""
Onboarding orchestrator: scrape pages → ask OpenClaw to extract structured
business info → save profile → produce a human-readable WhatsApp summary.
"""
from __future__ import annotations

import json
import re

from loguru import logger

from app.services import business_profile, scrape
from app.services.business_profile import BrandKit, BusinessProfile
from app.services.openclaw import ask_openclaw


_EXTRACTION_PROMPT = """You are a business-info extraction agent. \
The user owns a business and shared a public link. We scraped the page(s) and \
collected text + brand colors below. Your job: return STRICT JSON ONLY (no prose, \
no markdown fences) with this exact shape:

{
  "name": "...",                  // business name, null if unknown
  "type": "...",                  // restaurant | clinic | salon | retail | service | ...
  "category": "...",              // free-form sub-category, null if unsure
  "description": "...",           // 1-2 sentence pitch
  "city": "...",                  // city name, null if unknown
  "address": "...",               // full address if present, else null
  "phone": "...",                 // contact phone in E.164 if possible, else null
  "email": "...",                 // null if absent
  "socials": {"instagram": "...", "facebook": "...", "youtube": "..."},
  "timings": "...",               // e.g. "Mon-Sat 10am-9pm"
  "services": ["..."],            // up to 8 services / offerings
  "pricing_note": "...",          // null if no pricing visible
  "brand": {
    "primary_color": "#hex",      // pick from brand_colors list, null if unsure
    "secondary_color": "#hex",
    "accent_color": "#hex",
    "tone": "...",                // playful | professional | warm | luxury | ...
    "visual_style": "...",        // modern | minimal | vibrant | classic | ...
    "tagline": "..."              // a slogan if found, else null
  },
  "confidence": "high"            // high | medium | low — how complete the info is
}

Rules:
- Output JSON only, starting with { and ending with }.
- Use null (not empty string) for fields you cannot fill.
- Prefer values literally present in the text over guesses.
- For brand colors, pick from the provided list. Don't invent hex codes.
"""


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

    combined_text = "\n\n".join(combined_text_parts)[:20000]
    if not combined_text.strip():
        # nothing fetched — return a low-confidence profile so user sees the failure
        prof = BusinessProfile(phone=phone, source_urls=[url], confidence="low")
        business_profile.put(prof)
        return prof, (
            "I couldn't fetch any content from that link. "
            "Some sites block automated access (Instagram, Facebook). "
            "Try sharing your website URL or business Google Maps link."
        )

    llm_input = (
        f"{_EXTRACTION_PROMPT}\n\n"
        f"--- BRAND COLORS FOUND (pick from these) ---\n"
        f"{', '.join(all_colors[:20]) if all_colors else '(none)'}\n\n"
        f"--- PAGE CONTENT ---\n{combined_text}"
    )

    try:
        raw_reply = await ask_openclaw(llm_input, to=phone, timeout=180)
    except Exception:
        logger.exception("onboarding LLM call failed")
        raw_reply = ""

    parsed = _parse_json(raw_reply)
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


_JSON_BLOCK_RE = re.compile(r"\{[\s\S]*\}")


def _parse_json(text: str) -> dict:
    if not text:
        return {}
    # the agent might wrap JSON in markdown fences or prose — extract first {...} block
    m = _JSON_BLOCK_RE.search(text)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        # try to be forgiving: trim trailing prose
        depth = 0
        end = -1
        blob = m.group(0)
        for i, ch in enumerate(blob):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end > 0:
            try:
                return json.loads(blob[:end])
            except json.JSONDecodeError:
                pass
    return {}


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
