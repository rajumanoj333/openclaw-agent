"""
Marketing-poster generator using Gemini 2.5 Flash Image (Nano Banana).

The function builds a brand-aware prompt from the user's BusinessProfile
(colors, tone, logo description, services, tagline) and asks Gemini to
generate a 9:16 social-media poster. Returns raw image bytes + mime so the
caller can save to disk and serve via the existing /audio static route.
"""
from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from app.config import settings
from app.services.business_profile import BusinessProfile


def _hero_subject_for(brief: str, profile: BusinessProfile | None) -> str:
    """
    Derive a concrete photographic subject from the user's brief + business
    type. Image models render a clear *thing* much better than abstract text.
    """
    biz_type = ((profile.type or "") + " " + (profile.category or "")).lower() if profile else ""
    b = brief.lower()

    # Heuristic mapping: business type → hero photo subject
    if any(k in biz_type for k in ("baby", "kid", "toy", "child")):
        return "a smiling baby playing with colorful toys, soft pastel props"
    if any(k in biz_type for k in ("food", "restaurant", "cafe", "bakery", "pizza")):
        return "an oversized appetizing dish on a glossy plate, steam rising"
    if any(k in biz_type for k in ("salon", "beauty", "spa")):
        return "a glowing close-up of skincare products beside a tranquil model"
    if any(k in biz_type for k in ("fashion", "apparel", "clothing")):
        return "a stylish model in a modern outfit, editorial pose"
    if any(k in biz_type for k in ("clinic", "health", "medical")):
        return "a confident smiling person in a clinic setting, soft natural light"
    if any(k in biz_type for k in ("tech", "software", "saas")):
        return "a sleek device or abstract glowing interface, futuristic minimal"
    # Brief-based fallback
    if "diwali" in b:
        return "ornate diyas and rangoli with festive sparkle"
    if any(k in b for k in ("sale", "offer", "discount")):
        return "an elegant product hero shot with a subtle price-tag accent"
    return "a hero product photograph, premium commercial style"


def _build_prompt(brief: str, profile: BusinessProfile | None) -> str:
    """
    KFC-style structured prompt. Sections in order: scene → subject →
    composition → typography → tagline → palette. Image model renders each
    section as a separate visual ingredient.
    """
    name = (profile.name if profile else None) or "the business"
    tone = (profile.brand.tone if profile else None) or "modern"
    style = (profile.brand.visual_style if profile else None) or "premium editorial"
    tagline = (profile.brand.tagline if profile else None) or ""
    services = ", ".join(profile.services[:3]) if profile and profile.services else ""

    colors: list[str] = []
    if profile:
        colors = [
            c for c in (
                profile.brand.primary_color,
                profile.brand.secondary_color,
                profile.brand.accent_color,
            ) if c
        ] or profile.raw_colors[:3]

    primary = colors[0] if colors else "#cc0066"
    secondary = colors[1] if len(colors) > 1 else "#ffce00"

    hero = _hero_subject_for(brief, profile)

    sections = [
        # 1. Scene
        f"A high-end studio advertisement poster for {name}, "
        f"shot in {style} style with {tone} mood. "
        f"Background: smooth gradient from {primary} to {secondary} with soft "
        f"diffused lighting and subtle reflections.",

        # 2. Hero subject
        f"Centered hero subject: {hero}. "
        f"{f'Subtle accents referencing: {services}.' if services else ''}",

        # 3. Composition
        "Composition: ultra-sharp, cinematic lighting, premium commercial "
        "photography style, shallow depth of field, hyper-realistic textures, "
        "8K detail, vertical 9:16 layout, ample negative space at top and bottom.",

        # 4. Typography (large brand name)
        f"Large bold typography in the upper area: \"{name.upper()}\" — clean "
        f"display sans-serif, tight kerning, in {primary} or pure white for "
        f"maximum contrast against the gradient.",

        # 5. Headline / brief
        f"Sub-headline beneath the brand name: \"{brief.strip()[:80]}\" — "
        f"smaller editorial serif, single line, all letters readable.",

        # 6. Tagline
        f"Tagline at the bottom in small caps: \"{tagline or _default_tagline(brief)}\".",

        # 7. Constraints
        "No lorem ipsum, no sample placeholder text, no garbled letters, "
        "no watermarks, no extra logos. Every word must be a real, correctly "
        "spelled word. Premium magazine-cover finish.",
    ]
    return " ".join(s.strip() for s in sections if s.strip())


def _default_tagline(brief: str) -> str:
    b = brief.lower()
    if "diwali" in b:
        return "Light up your celebrations."
    if any(k in b for k in ("sale", "offer", "discount")):
        return "Limited time only."
    if any(k in b for k in ("launch", "new", "introducing")):
        return "Now in stores."
    return "Made for you."


async def generate_poster(
    brief: str,
    profile: BusinessProfile | None = None,
) -> tuple[bytes, str]:
    """
    Returns (image_bytes, mime_type). Raises RuntimeError on failure.

    Pipeline:
      1. Build brand-aware prompt
      2. Try Gemini → fall back to Pollinations on quota
      3. If profile has a logo URL, composite it onto the generated image
    """
    prompt = _build_prompt(brief, profile)

    if not settings.gemini_key:
        logger.info("GEMINI_API_KEY missing — using Pollinations fallback")
        image, mime = await _pollinations(prompt)
    else:
        try:
            image, mime = await _gemini_generate(prompt)
        except Exception as e:
            msg = str(e)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower():
                logger.warning(f"gemini quota — falling back to Pollinations: {e!r}")
                image, mime = await _pollinations(prompt)
            else:
                raise

    if profile and profile.logo_url:
        try:
            image, mime = await _overlay_logo(image, mime, profile.logo_url)
        except Exception:
            logger.exception("logo overlay failed; returning poster without logo")

    return image, mime


async def _overlay_logo(
    poster_bytes: bytes,
    poster_mime: str,
    logo_url: str,
) -> tuple[bytes, str]:
    """
    Fetch the business logo and paste it onto the bottom-center of the
    generated poster. Always returns PNG to preserve transparency.
    """
    import io
    import asyncio
    import httpx
    from PIL import Image

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        resp = await client.get(logo_url, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        logo_bytes = resp.content

    def _composite() -> bytes:
        poster = Image.open(io.BytesIO(poster_bytes)).convert("RGBA")
        logo = Image.open(io.BytesIO(logo_bytes)).convert("RGBA")

        # scale logo to ~14% of poster width, preserve aspect
        target_w = max(120, int(poster.width * 0.14))
        ratio = target_w / logo.width
        target_h = int(logo.height * ratio)
        logo = logo.resize((target_w, target_h), Image.LANCZOS)

        # white rounded badge behind logo for legibility
        pad = max(8, int(target_w * 0.08))
        badge = Image.new(
            "RGBA",
            (target_w + pad * 2, target_h + pad * 2),
            (255, 255, 255, 230),
        )

        # bottom-center placement, ~5% from edge
        x = (poster.width - badge.width) // 2
        y = poster.height - badge.height - int(poster.height * 0.05)

        poster.alpha_composite(badge, (x, y))
        poster.alpha_composite(logo, (x + pad, y + pad))

        out = io.BytesIO()
        poster.convert("RGB").save(out, format="PNG", optimize=True)
        return out.getvalue()

    composed = await asyncio.to_thread(_composite)
    logger.info(f"logo overlay applied bytes={len(composed)}")
    return composed, "image/png"


async def _pollinations(prompt: str) -> tuple[bytes, str]:
    """
    Free image generation via https://image.pollinations.ai/prompt/<text>
    No auth, no quota, returns JPEG.

    Model = `flux` — better fidelity + typography vs default `turbo`.
    Slower (~10-25s) but readable headlines + brand colors.
    """
    import re

    import httpx
    from urllib.parse import quote

    # Flatten newlines (Pollinations 404s on multi-line URLs) but keep
    # comma+sentence structure so the model still parses sections.
    flat = re.sub(r"\s+", " ", prompt).strip()[:1500]

    model = "flux"
    url = (
        f"https://image.pollinations.ai/prompt/{quote(flat)}"
        f"?width=768&height=1280&nologo=true&model={model}&enhance=true"
    )
    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
    logger.info(
        f"pollinations image bytes={len(resp.content)} model={model} "
        f"prompt_chars={len(flat)}"
    )
    return resp.content, "image/jpeg"


async def _gemini_generate(prompt: str) -> tuple[bytes, str]:
    """Original Gemini path, kept as primary when quota allows."""
    def _run() -> tuple[bytes, str]:
        # Lazy import: keeps app boot snappy if Gemini key isn't configured yet.
        from google import genai

        client = genai.Client(api_key=settings.gemini_key)

        # Gemini image-generation models accept a plain prompt and return
        # candidates whose `parts` contain `inline_data` with the image bytes.
        response = client.models.generate_content(
            model=settings.gemini_image_model,
            contents=[prompt],
        )

        candidates = getattr(response, "candidates", None) or []
        for cand in candidates:
            content = getattr(cand, "content", None)
            if not content:
                continue
            for part in getattr(content, "parts", None) or []:
                inline = getattr(part, "inline_data", None)
                if inline and getattr(inline, "data", None):
                    data: Any = inline.data
                    # Some SDK versions return raw bytes; older versions returned
                    # base64-encoded strings. Normalize.
                    if isinstance(data, str):
                        import base64
                        data = base64.b64decode(data)
                    mime = getattr(inline, "mime_type", None) or "image/png"
                    return data, mime

        # If we got here, the response had no image — surface useful debug info
        text_blob = ""
        for cand in candidates:
            for part in getattr(getattr(cand, "content", None), "parts", None) or []:
                t = getattr(part, "text", None)
                if t:
                    text_blob += t
        raise RuntimeError(
            f"Gemini returned no image. text_response={text_blob[:300]!r}"
        )

    image, mime = await asyncio.to_thread(_run)
    logger.info(f"gemini poster bytes={len(image)} mime={mime}")
    return image, mime
