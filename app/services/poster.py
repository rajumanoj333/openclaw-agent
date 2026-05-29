"""
Marketing-poster generator using Gemini 2.5 Flash Image (Nano Banana).

The function builds a brand-aware prompt from the user's BusinessProfile
(colors, tone, logo description, services, tagline) and asks Gemini to
generate a 9:16 social-media poster. Returns raw image bytes + mime so the
caller can save to disk and serve via the existing /audio static route.
"""
from __future__ import annotations

import asyncio
import time

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
    Returns (image_bytes, mime_type).

    Production architecture: Fal AI is the ONLY image generator.
    FLUX schnell, ~3-6s per call, single retry on transient 5xx.
    Raises RuntimeError if Fal fails after retries — caller surfaces
    the error to the user (no silent quality degradation through
    fallback chains).

    Brand badge (logo or typographic wordmark) is always composited
    onto the result.
    """
    if not settings.fal_api_key.strip():
        raise RuntimeError(
            "FAL_API_KEY missing from .env — image generation disabled. "
            "Add the key and restart FastAPI."
        )

    prompt = _build_prompt(brief, profile)
    image, mime = await _fal_generate(prompt)
    logger.info(f"poster engine=fal model={settings.fal_image_model}")

    # Brand presence is non-negotiable per design: every poster carries
    # the business mark, even when the upstream logo URL is unreachable.
    # 1) Try real logo composite. 2) Fall back to a typographic wordmark
    # drawn from the business name. Either way, the bare AI image never
    # ships without a branded badge.
    biz_name = (profile.name if profile else None) or ""
    image, mime = await _apply_brand_badge(
        image, mime or "image/jpeg",
        logo_url=profile.logo_url if profile else None,
        business_name=biz_name,
    )
    return image, mime


async def _apply_brand_badge(
    poster_bytes: bytes,
    poster_mime: str,
    *,
    logo_url: str | None,
    business_name: str,
) -> tuple[bytes, str]:
    """
    Guarantee every poster ships with a branded badge.

    1. If `logo_url` is set, try to fetch + composite the image logo.
       Retries with multiple User-Agent headers — some CDNs 403 on the
       default httpx UA but accept a browser UA.
    2. If the logo fetch fails OR no logo URL exists, fall back to a
       typographic wordmark drawn from `business_name` on the white badge.
    3. As a last resort (empty name AND no logo), apply a small
       "Powered by Morpheus" badge so the poster never ships bare.
    """
    logo_bytes: bytes | None = None
    if logo_url:
        logo_bytes = await _fetch_logo_bytes(logo_url)

    return await asyncio.to_thread(
        _compose_branded_poster,
        poster_bytes,
        logo_bytes,
        business_name,
    )


async def _fetch_logo_bytes(logo_url: str) -> bytes | None:
    """
    Attempt logo download with rotating User-Agents. Returns bytes on
    success, None if every attempt failed (caller falls back to text).
    """
    import httpx

    user_agents = [
        # Modern desktop Chrome — most CDNs whitelist this.
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        # Mobile Safari — some CDNs route differently.
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        # Default httpx — last resort.
        "Mozilla/5.0",
    ]
    for ua in user_agents:
        try:
            async with httpx.AsyncClient(
                timeout=12.0, follow_redirects=True
            ) as client:
                r = await client.get(logo_url, headers={"User-Agent": ua})
            if r.status_code == 200 and r.content and len(r.content) > 200:
                logger.info(
                    f"logo fetched bytes={len(r.content)} url={logo_url[:80]}"
                )
                return r.content
            logger.warning(
                f"logo fetch HTTP {r.status_code} ua={ua[:30]}..."
            )
        except Exception as e:
            logger.warning(f"logo fetch err ua={ua[:30]}...: {e!r}")
    logger.warning(f"all logo fetch attempts failed url={logo_url}")
    return None


def _compose_branded_poster(
    poster_bytes: bytes,
    logo_bytes: bytes | None,
    business_name: str,
) -> tuple[bytes, str]:
    """Synchronous Pillow composite. Always returns PNG."""
    import io
    from PIL import Image, ImageDraw, ImageFont

    poster = Image.open(io.BytesIO(poster_bytes)).convert("RGBA")
    pw, ph = poster.size

    # Sizing rules: badge width = 22% of poster for text wordmarks,
    # 16% for image logos (image logos look heavier).
    text_mode = logo_bytes is None
    badge_w = int(pw * (0.42 if text_mode else 0.20))

    if text_mode:
        # Text wordmark — draw business name (or generic) on white pill.
        wordmark = (business_name or "Powered by Morpheus").strip()
        # Font size scales to badge width
        font_size = max(20, int(badge_w * 0.13))
        font = _load_font(font_size)
        dummy = Image.new("RGBA", (1, 1))
        bbox = ImageDraw.Draw(dummy).textbbox((0, 0), wordmark, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        pad_x = max(20, int(text_w * 0.18))
        pad_y = max(14, int(text_h * 0.6))
        badge_w = text_w + pad_x * 2
        badge_h = text_h + pad_y * 2
        badge = Image.new("RGBA", (badge_w, badge_h), (255, 255, 255, 235))
        d = ImageDraw.Draw(badge)
        d.text(
            (pad_x, pad_y - bbox[1]),
            wordmark,
            fill=(15, 18, 25, 255),
            font=font,
        )
        logo_layer = None
    else:
        # Image logo — resize to fit inside badge.
        logo = Image.open(io.BytesIO(logo_bytes)).convert("RGBA")
        target_w = badge_w
        ratio = target_w / logo.width
        target_h = int(logo.height * ratio)
        logo = logo.resize((target_w, target_h), Image.LANCZOS)
        pad = max(10, int(target_w * 0.10))
        badge = Image.new(
            "RGBA",
            (target_w + pad * 2, target_h + pad * 2),
            (255, 255, 255, 235),
        )
        badge_w, badge_h = badge.size
        logo_layer = logo

    # Bottom-center placement with ~5% margin
    x = (pw - badge_w) // 2
    y = ph - badge_h - int(ph * 0.05)

    poster.alpha_composite(badge, (x, y))
    if logo_layer is not None:
        # pad value is the same we used above
        pad = max(10, int(logo_layer.width * 0.10))
        poster.alpha_composite(logo_layer, (x + pad, y + pad))

    out = io.BytesIO()
    poster.convert("RGB").save(out, format="PNG", optimize=True)
    logger.info(
        f"brand badge applied mode={'text' if text_mode else 'logo'} "
        f"bytes={out.tell()}"
    )
    return out.getvalue(), "image/png"


def _load_font(size: int):
    """Try a few common system fonts; fall back to PIL's default."""
    from PIL import ImageFont

    candidates = [
        # Windows
        "C:/Windows/Fonts/segoeuib.ttf",  # Segoe UI Bold
        "C:/Windows/Fonts/arialbd.ttf",   # Arial Bold
        # macOS / Linux
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


_FAL_BASE = "https://fal.run"
_FAL_MAX_PROMPT = 1500
_FAL_TIMEOUT_S = 60.0


async def _fal_generate(prompt: str) -> tuple[bytes, str]:
    """
    Fal AI image generation via the sync endpoint.

    Uses FLUX schnell by default — 4-step model, ~3-5s, portrait_16_9
    for social posters.

    Returns (jpeg_bytes, mime). Single retry on transient 5xx / network
    error before raising. Caller decides whether to surface the error
    to the user or degrade gracefully.

    The Fal response contains a CDN URL; we download the bytes so the
    downstream brand-badge composite step works on raw image data and
    the final composited result can be hosted alongside other media.
    """
    import re
    import unicodedata

    import httpx

    api_key = settings.fal_api_key.strip()
    if not api_key:
        raise RuntimeError("FAL_API_KEY missing")

    # Sanitize + cap prompt — Fal handles long prompts but ASCII-folded
    # text avoids any tokenizer quirks across models.
    flat = unicodedata.normalize("NFKD", prompt)
    flat = flat.encode("ascii", "ignore").decode("ascii")
    flat = re.sub(r"\s+", " ", flat).strip()[:_FAL_MAX_PROMPT]

    url = f"{_FAL_BASE}/{settings.fal_image_model}"
    headers = {
        "Authorization": f"Key {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "prompt": flat,
        "image_size": "portrait_16_9",
        "num_inference_steps": 4,
        "num_images": 1,
        "enable_safety_checker": True,
    }

    last_err: str = ""
    for attempt in (1, 2):
        t0 = time.time()
        try:
            async with httpx.AsyncClient(timeout=_FAL_TIMEOUT_S) as client:
                r = await client.post(url, json=body, headers=headers)

                # Auth + client errors — don't retry, surface immediately
                if r.status_code in (401, 403):
                    raise RuntimeError(
                        f"fal auth failed ({r.status_code}): check FAL_API_KEY"
                    )
                if 400 <= r.status_code < 500:
                    raise RuntimeError(
                        f"fal HTTP {r.status_code}: {r.text[:300]}"
                    )
                if r.status_code != 200:
                    # 5xx — retry once
                    last_err = f"HTTP {r.status_code}: {r.text[:200]}"
                    raise httpx.HTTPStatusError(
                        last_err, request=r.request, response=r,
                    )

                data = r.json()
                images = data.get("images") or []
                if not images or not images[0].get("url"):
                    raise RuntimeError(
                        f"fal no image in response: {str(data)[:200]}"
                    )

                cdn_url = images[0]["url"]
                gen_ms = int((time.time() - t0) * 1000)

                d = await client.get(cdn_url, timeout=30.0)
                d.raise_for_status()
                img_bytes = d.content
                mime = images[0].get("content_type") or "image/jpeg"

                logger.info(
                    f"fal generated bytes={len(img_bytes)} mime={mime} "
                    f"gen_ms={gen_ms} attempt={attempt} "
                    f"cdn={cdn_url[:60]}..."
                )
                return img_bytes, mime

        except RuntimeError:
            # explicit RuntimeError = non-retryable (auth, 4xx, bad shape)
            raise
        except (httpx.HTTPError, httpx.HTTPStatusError) as e:
            last_err = repr(e)
            if attempt == 1:
                logger.warning(f"fal attempt 1 failed: {last_err} — retrying")
                await asyncio.sleep(1.5)
                continue
            raise RuntimeError(f"fal failed after 2 attempts: {last_err}")

    raise RuntimeError(f"fal failed: {last_err}")


