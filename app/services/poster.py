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
    Compose a structured prompt that nudges Gemini toward on-brand output.
    """
    parts: list[str] = [
        "Generate a high-quality vertical (9:16) social-media marketing poster.",
        f"Topic / message: {brief.strip()}",
    ]

    if profile:
        if profile.name:
            parts.append(f"Business name: {profile.name}")
        if profile.type or profile.category:
            biz = " — ".join(x for x in (profile.type, profile.category) if x)
            parts.append(f"Business type: {biz}")
        if profile.services:
            parts.append(f"Featured services: {', '.join(profile.services[:3])}")
        if profile.brand.tagline:
            parts.append(f"Tagline to display prominently: \"{profile.brand.tagline}\"")
        if profile.brand.tone:
            parts.append(f"Brand tone of voice: {profile.brand.tone}")
        if profile.brand.visual_style:
            parts.append(f"Visual style: {profile.brand.visual_style}")

        colors = [
            c for c in (
                profile.brand.primary_color,
                profile.brand.secondary_color,
                profile.brand.accent_color,
            ) if c
        ]
        if not colors and profile.raw_colors:
            colors = profile.raw_colors[:3]
        if colors:
            parts.append(
                "Use these brand colors prominently in backgrounds, gradients, "
                f"and accents (don't deviate): {', '.join(colors)}"
            )

        if profile.brand.logo_description:
            parts.append(f"Logo: {profile.brand.logo_description}")

    parts.extend([
        "Composition: clean editorial layout, strong typography, ample contrast, "
        "no Lorem Ipsum text, no watermarks, no sample words.",
        "Output format: vertical 9:16, photorealistic where relevant, sharp readable headline.",
    ])

    return "\n".join(parts)


async def generate_poster(
    brief: str,
    profile: BusinessProfile | None = None,
) -> tuple[bytes, str]:
    """
    Returns (image_bytes, mime_type). Raises RuntimeError on failure.

    Tries Gemini first; falls back to Pollinations.ai (free, no-auth) on
    quota error or missing API key.
    """
    prompt = _build_prompt(brief, profile)

    if not settings.gemini_key:
        logger.info("GEMINI_API_KEY missing — using Pollinations fallback")
        return await _pollinations(prompt)

    try:
        return await _gemini_generate(prompt)
    except Exception as e:
        msg = str(e)
        if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower():
            logger.warning(f"gemini quota — falling back to Pollinations: {e!r}")
            return await _pollinations(prompt)
        raise


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
