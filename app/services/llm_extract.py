"""
Direct OpenRouter call for URL → BusinessProfile JSON extraction.

Why direct OpenRouter (not OpenClaw)?
  - Deterministic JSON extraction needs a strict schema enforcer +
    minimal context. OpenClaw on the VM injects ~12kb of workspace
    persona on every call ("blank-slate creature with a clipboard"...),
    plus its newer CLI nests responses inside {result:{payloads}} —
    fighting our prompt instead of helping it.
  - OpenRouter's `response_format` (JSON schema) makes the model
    physically unable to emit non-JSON. No prose, no markdown fences,
    no persona drift.
  - 3-5s round trip. Cheap (~$0.0001/extraction on gpt-4o-mini).

OpenClaw is still the brain for chat / agent reasoning. This module is
data-extraction only.
"""
from __future__ import annotations

import time
from typing import Any

import httpx
from loguru import logger

from app.config import settings


_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# JSON schema enforced server-side. Names match BusinessProfile dataclass.
_SCHEMA: dict[str, Any] = {
    "name": "business_profile",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "name":         {"type": ["string", "null"]},
            "type":         {"type": ["string", "null"]},
            "category":     {"type": ["string", "null"]},
            "description":  {"type": ["string", "null"]},
            "city":         {"type": ["string", "null"]},
            "address":      {"type": ["string", "null"]},
            "phone":        {"type": ["string", "null"]},
            "email":        {"type": ["string", "null"]},
            "socials": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "instagram": {"type": ["string", "null"]},
                    "facebook":  {"type": ["string", "null"]},
                    "youtube":   {"type": ["string", "null"]},
                    "twitter":   {"type": ["string", "null"]},
                    "linkedin":  {"type": ["string", "null"]},
                },
                "required": ["instagram", "facebook", "youtube", "twitter", "linkedin"],
            },
            "timings":      {"type": ["string", "null"]},
            "services":     {"type": "array", "items": {"type": "string"}},
            "pricing_note": {"type": ["string", "null"]},
            "brand": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "primary_color":   {"type": ["string", "null"]},
                    "secondary_color": {"type": ["string", "null"]},
                    "accent_color":    {"type": ["string", "null"]},
                    "tone":            {"type": ["string", "null"]},
                    "visual_style":    {"type": ["string", "null"]},
                    "tagline":         {"type": ["string", "null"]},
                },
                "required": ["primary_color", "secondary_color", "accent_color",
                             "tone", "visual_style", "tagline"],
            },
            "confidence":   {"type": "string", "enum": ["high", "medium", "low"]},
        },
        "required": ["name", "type", "category", "description", "city",
                     "address", "phone", "email", "socials", "timings",
                     "services", "pricing_note", "brand", "confidence"],
    },
}


_SYSTEM = (
    "You extract business information from scraped web pages and return "
    "ONLY a JSON object that fits the business_profile schema. Use null "
    "for fields not present in the text. Pick brand colors from the "
    "provided BRAND_COLORS list only — never invent hex codes. Confidence "
    "reflects how much of the schema is populated."
)


def _user_prompt(text: str, colors: list[str]) -> str:
    color_line = ", ".join(colors[:20]) if colors else "(none)"
    return (
        f"BRAND_COLORS: {color_line}\n\n"
        f"--- SCRAPED TEXT ---\n{text}\n--- END ---"
    )


async def extract_profile(text: str, colors: list[str]) -> dict[str, Any]:
    """
    Extract business profile JSON from scraped text via OpenRouter.
    Returns {} on any failure — caller surfaces empty profile + banner
    asking user to retry or fill manually.
    """
    api_key = (settings.openrouter_api_key or "").strip()
    if not api_key:
        logger.warning("OPENROUTER_API_KEY missing — extraction skipped")
        return {}
    if not text.strip():
        return {}

    body = {
        "model": settings.openrouter_extract_model,
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": _user_prompt(text[:8000], colors)},
        ],
        "response_format": {"type": "json_schema", "json_schema": _SCHEMA},
        "temperature": 0.1,
        "max_tokens": 1500,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/rajumanoj333/openclaw-agent",
        "X-Title": "Morpheus Onboarding",
    }

    t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            r = await client.post(_OPENROUTER_URL, json=body, headers=headers)
    except Exception as e:
        logger.warning(f"openrouter extract transport: {e!r}")
        return {}

    ms = int((time.time() - t0) * 1000)
    if r.status_code != 200:
        logger.warning(
            f"openrouter extract HTTP {r.status_code} ms={ms}: "
            f"{r.text[:300]}"
        )
        return {}

    try:
        payload = r.json()
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as e:
        logger.warning(f"openrouter extract bad shape: {e!r}")
        return {}

    import json
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as e:
        # Should not happen with response_format=json_schema, but guard anyway
        logger.warning(f"openrouter extract bad JSON: {e!r} head={content[:200]!r}")
        return {}

    logger.info(
        f"openrouter extract OK ms={ms} model={settings.openrouter_extract_model} "
        f"name={parsed.get('name')!r} conf={parsed.get('confidence')}"
    )
    return parsed
