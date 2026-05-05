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


def _build_prompt(brief: str, profile: BusinessProfile | None) -> str:
    """
    Compose a rich, marketing-grade prompt for the image model.
    Aim: a poster a real designer would ship, on-brand and on-message.
    """
    name = (profile.name if profile else None) or "the business"
    biz_type = ""
    if profile:
        biz_type = " — ".join(x for x in (profile.type, profile.category) if x)

    services = ", ".join(profile.services[:3]) if profile and profile.services else ""
    tagline = profile.brand.tagline if profile and profile.brand.tagline else ""
    tone = profile.brand.tone if profile and profile.brand.tone else "modern"
    style = profile.brand.visual_style if profile and profile.brand.visual_style else "clean editorial"

    colors: list[str] = []
    if profile:
        colors = [
            c for c in (
                profile.brand.primary_color,
                profile.brand.secondary_color,
                profile.brand.accent_color,
            ) if c
        ]
        if not colors:
            colors = profile.raw_colors[:3]
    color_phrase = (
        f"Use these exact brand colors as the dominant palette (no other hues): {', '.join(colors)}."
        if colors else ""
    )

    return (
        f"Professional marketing poster for {name}"
        f"{f', a {biz_type}' if biz_type else ''}.\n"
        f"Headline message: \"{brief.strip()}\".\n"
        f"{f'Tagline overlay: \"{tagline}\". ' if tagline else ''}"
        f"{f'Featured: {services}. ' if services else ''}"
        f"Tone: {tone}. Visual style: {style}.\n"
        f"{color_phrase}\n"
        f"Composition: vertical 9:16, large bold headline at top in a serif "
        f"or geometric sans display font, secondary line beneath, subject "
        f"or product photography occupying the middle 60%, brand-color "
        f"accents and gradients, clean negative space at the bottom for a "
        f"call-to-action button. Strong contrast, premium feel, magazine-cover "
        f"quality. No watermarks, no lorem ipsum, no sample placeholder text, "
        f"no logos other than the implied brand mark.\n"
        f"Lighting: dramatic studio or editorial. Make the headline text "
        f"crisp and legible — short, punchy, no spelling errors."
    )


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
    No auth, no quota, returns JPEG. Slower (~5-15s) but reliable for demo.
    """
    import re

    import httpx
    from urllib.parse import quote

    # Flatten to single line + cap length — Pollinations 404s on overly long
    # URLs with newlines.
    flat = re.sub(r"\s+", " ", prompt).strip()[:600]

    url = (
        f"https://image.pollinations.ai/prompt/{quote(flat)}"
        f"?width=768&height=1280&nologo=true"
    )
    async with httpx.AsyncClient(timeout=90.0, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
    logger.info(f"pollinations image bytes={len(resp.content)}")
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
