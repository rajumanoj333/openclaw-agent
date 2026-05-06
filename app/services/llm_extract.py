"""
Fast LLM extraction via Gemini 2.5 Flash.

Bypasses OpenClaw for the URL → BusinessProfile JSON step (pure structured-data
work) so onboarding stays sub-5s instead of waiting on the slow OpenClaw
embedded fallback. OpenClaw is reserved for actual chat / task execution.

Per-URL cache (sha256, 1h TTL) makes repeat scrapes instant.
"""
from __future__ import annotations

import hashlib
import json
import re
import time

import httpx
from loguru import logger

from app.config import settings


_CACHE_TTL = 60 * 60
_cache: dict[str, tuple[float, dict]] = {}

_PRIMARY_MODEL = "gemini-2.5-flash"
_FALLBACK_MODELS = ("gemini-2.0-flash", "gemini-1.5-flash")

_EXTRACTION_PROMPT = """You are a business-info extractor. Return STRICT JSON ONLY \
(no prose, no markdown fences) matching this exact shape:

{
  "name": "...",
  "type": "...",
  "category": "...",
  "description": "...",
  "city": "...",
  "address": "...",
  "phone": "...",
  "email": "...",
  "socials": {"instagram": "...", "facebook": "...", "youtube": "..."},
  "timings": "...",
  "services": ["..."],
  "pricing_note": "...",
  "brand": {
    "primary_color": "#hex",
    "secondary_color": "#hex",
    "accent_color": "#hex",
    "tone": "...",
    "visual_style": "...",
    "tagline": "..."
  },
  "confidence": "high"
}

Rules:
- Output JSON only — start with { and end with }.
- Use null (not empty string) for missing fields.
- Prefer values literally present in the text over guesses.
- For brand colors, pick from the provided list. Never invent hex codes.
- "confidence" reflects how complete the extraction is: high | medium | low.
"""


def _cache_key(url: str, text: str) -> str:
    h = hashlib.sha256()
    h.update(url.encode("utf-8", errors="ignore"))
    h.update(b"\0")
    h.update(text[:500].encode("utf-8", errors="ignore"))
    return h.hexdigest()


def _trim_text(text: str, max_chars: int = 8000) -> str:
    """Keep mostly the head (where 'about' lives) plus a tail snippet."""
    if len(text) <= max_chars:
        return text
    head = text[: int(max_chars * 0.75)]
    tail = text[-int(max_chars * 0.25):]
    return f"{head}\n…\n{tail}"


async def extract_profile(
    *, url: str, text: str, colors: list[str], timeout: float = 25.0
) -> dict:
    """
    Run Gemini extraction. Returns a dict on success, {} on any failure
    (caller falls back to a low-confidence empty profile so the wizard
    can still proceed with manual fields).
    """
    key = settings.gemini_key
    if not key:
        logger.warning("GEMINI_API_KEY missing — skipping LLM extraction")
        return {}

    if not text.strip():
        return {}

    ck = _cache_key(url, text)
    now = time.time()
    cached = _cache.get(ck)
    if cached and now - cached[0] < _CACHE_TTL:
        logger.info(f"llm_extract cache hit url={url}")
        return cached[1]

    user_block = (
        "--- BRAND COLORS FOUND (pick from these only) ---\n"
        f"{', '.join(colors[:20]) if colors else '(none)'}\n\n"
        "--- PAGE CONTENT ---\n"
        f"{_trim_text(text)}"
    )
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": _EXTRACTION_PROMPT + "\n\n" + user_block}],
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.2,
            "maxOutputTokens": 1500,
        },
    }

    parsed = await _call_gemini(payload, key, timeout=timeout)
    if parsed:
        _cache[ck] = (now, parsed)
    return parsed


async def _call_gemini(payload: dict, key: str, *, timeout: float) -> dict:
    """Try primary model, then fall back through cheaper variants on quota/4xx."""
    for model in (_PRIMARY_MODEL, *_FALLBACK_MODELS):
        api_url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={key}"
        )
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                t0 = time.time()
                r = await client.post(api_url, json=payload)
                ms = int((time.time() - t0) * 1000)
        except Exception as e:
            logger.warning(f"gemini {model} call failed: {e!r}")
            continue

        if r.status_code == 429:
            logger.warning(f"gemini {model} quota exhausted — falling back")
            continue
        if r.status_code >= 400:
            logger.warning(f"gemini {model} {r.status_code}: {r.text[:200]}")
            continue

        try:
            data = r.json()
            text = (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
            )
        except Exception as e:
            logger.warning(f"gemini {model} bad response shape: {e!r}")
            continue

        logger.info(f"gemini extract ok model={model} ms={ms} chars={len(text)}")
        return _parse_json(text)

    return {}


_JSON_BLOCK_RE = re.compile(r"\{[\s\S]*\}")


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
        # forgiving: trim trailing prose past the matched first balanced {...}
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
