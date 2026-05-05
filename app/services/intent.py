"""
Lightweight intent classifier for inbound user messages.

Rule-based first (cheap, deterministic). When ambiguous we fall back to
the agent itself. Used to route a WhatsApp message to the right handler:

  - chat        : ordinary Q&A → OpenClaw
  - onboarding  : URL detected → scrape + extract
  - poster      : "make me a poster" / "design a creative" → Gemini
  - confirm     : yes / haan / ఔను
  - cancel      : no / cancel
"""
from __future__ import annotations

import re
from typing import Literal

Intent = Literal["chat", "poster", "confirm", "cancel"]


_POSTER_PATTERNS = [
    r"\b(?:make|create|design|generate|build)\b.*\b(?:poster|creative|flyer|banner|ad|graphic|image)\b",
    r"\b(?:poster|creative|flyer|banner)\b.*\bfor\b",
    r"\bdesign\s+(?:a|an|the)\b",
    r"\bnano\s*banana\b",
]
_POSTER_RE = re.compile("|".join(_POSTER_PATTERNS), re.IGNORECASE)

_CONFIRM_WORDS = {
    "yes", "y", "yeah", "yep", "ok", "okay", "confirm", "go", "do it",
    "ఔను", "హా", "हाँ", "हां", "ಹೌದು", "ஆம்",
}
_CANCEL_WORDS = {
    "no", "n", "nope", "cancel", "stop", "abort",
    "కాదు", "नहीं", "இல்லை", "ಇಲ್ಲ",
}


def classify(text: str) -> Intent:
    t = (text or "").strip().lower()
    if not t:
        return "chat"

    # short-word match first (cheap)
    if t in _CONFIRM_WORDS:
        return "confirm"
    if t in _CANCEL_WORDS:
        return "cancel"

    if _POSTER_RE.search(t):
        return "poster"

    return "chat"
