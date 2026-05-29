"""
Onboarding orchestrator: scrape → ask OpenClaw to extract structured business
info → save profile → produce a human-readable WhatsApp summary.

OpenClaw is the only extraction path. The VM must be up; on failure we
return an empty profile so the user sees the failure and can retry / fill
manually instead of getting silently-wrong data from a second LLM.
"""
from __future__ import annotations

import json
import re

from loguru import logger

from app.services import business_profile, scrape
from app.services.business_profile import BrandKit, BusinessProfile
from app.services.openclaw import ask_openclaw_raw


_OPENCLAW_EXTRACT_TIMEOUT = 120

# How much scraped text to send. openrouter/auto picks weaker models on
# huge payloads + the model loses the JSON schema instruction in the tail.
# 6k chars covers the homepage + about/contact preview.
_MAX_SCRAPE_CHARS = 6000

# Smaller schema in the prompt — keep it parseable for weaker models too.
_OPENCLAW_PROMPT = """Extract business info from the text below. Reply with \
JSON ONLY — no prose, no markdown fences, no commentary.

Use this exact shape (use null for missing fields):
{"name":"...","type":"...","category":null,"description":"...","city":null,"address":null,"phone":null,"email":null,"socials":{},"timings":null,"services":[],"pricing_note":null,"brand":{"primary_color":null,"secondary_color":null,"accent_color":null,"tone":null,"visual_style":null,"tagline":null},"confidence":"high"}

Rules:
- Output starts with { and ends with }. Nothing else.
- Pick brand colors from the BRAND_COLORS list only. Never invent hex codes.
- Skip Product/Article schemas; only use Organization/Business signals.
"""

# Lines starting with these markers are removed from scraped text before
# sending — they're our own enrichment tags that can confuse models that
# don't follow nested JSON well.
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

    parsed = await _extract_via_openclaw(combined_text, all_colors)
    logger.info(
        f"onboarding extraction phone={phone} via=openclaw "
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


_JSON_BLOCK_RE = re.compile(r"\{[\s\S]*\}")


async def _extract_via_openclaw(text: str, colors: list[str]) -> dict:
    """
    Call OpenClaw with the extraction prompt. Single retry with HALF the
    text on parse failure — long prompts cause models to drop the JSON
    instruction. Returns {} after retries are exhausted; UI surfaces an
    empty profile + manual-fill banner.
    """
    if not text.strip():
        return {}

    # Order matters: put the prompt LAST so it's the freshest instruction
    # in the model's context window. Many models bias toward the most
    # recent prompt segment.
    colors_line = ", ".join(colors[:20]) if colors else "(none)"

    for attempt, text_chunk in enumerate([text, text[: len(text) // 2]], start=1):
        payload = (
            f"BRAND_COLORS: {colors_line}\n\n"
            f"--- PAGE CONTENT ---\n{text_chunk}\n--- END ---\n\n"
            f"{_OPENCLAW_PROMPT}"
        )
        try:
            raw = await ask_openclaw_raw(
                payload, to=None, timeout=_OPENCLAW_EXTRACT_TIMEOUT
            )
        except Exception as e:
            logger.warning(f"openclaw extraction attempt {attempt} failed: {e!r}")
            continue

        parsed = _parse_json(raw)
        if parsed.get("name"):
            logger.info(
                f"extraction attempt {attempt} OK chars={len(payload)} "
                f"reply_chars={len(raw)} keys={list(parsed.keys())}"
            )
            return parsed
        logger.warning(
            f"extraction attempt {attempt} parsed but empty — reply head: "
            f"{raw[:200]!r}"
        )

    return {}


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


def _parse_json(text: str) -> dict:
    if not text:
        return {}
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    m = _JSON_BLOCK_RE.search(text)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        # forgiving: trim trailing prose past the first balanced {...}
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
