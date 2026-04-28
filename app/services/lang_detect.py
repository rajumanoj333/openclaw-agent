"""
Cheap language detection from text using Unicode block ranges.

Returns BCP-47 codes that match Sarvam / Google TTS expectations.
Used to override the noisy `language_code` Sarvam STT returns when its
codemix mode mislabels English audio.
"""
from __future__ import annotations


_BLOCKS: tuple[tuple[str, str, str], ...] = (
    ("te-IN", "ఀ", "౿"),  # Telugu
    ("hi-IN", "ऀ", "ॿ"),  # Devanagari (Hindi/Marathi)
    ("ta-IN", "஀", "௿"),  # Tamil
    ("kn-IN", "ಀ", "೿"),  # Kannada
    ("ml-IN", "ഀ", "ൿ"),  # Malayalam
    ("bn-IN", "ঀ", "৿"),  # Bengali
    ("gu-IN", "઀", "૿"),  # Gujarati
    ("pa-IN", "਀", "੿"),  # Gurmukhi (Punjabi)
    ("or-IN", "଀", "୿"),  # Odia
)


def detect_lang(text: str, hint: str | None = None) -> str:
    """
    Returns the dominant language code based on Unicode block matches.
    Falls back to `hint` (when valid) or `en-IN` for ASCII-only text.
    """
    if not text:
        return _normalize(hint) or "en-IN"

    counts = {code: 0 for code, _, _ in _BLOCKS}
    ascii_letters = 0
    for ch in text:
        if "a" <= ch.lower() <= "z":
            ascii_letters += 1
            continue
        for code, lo, hi in _BLOCKS:
            if lo <= ch <= hi:
                counts[code] += 1
                break

    best_code, best_count = max(counts.items(), key=lambda kv: kv[1])
    if best_count > 0:
        return best_code

    # No Indic script and any ASCII letters → trust English over the noisy hint
    if ascii_letters > 0:
        return "en-IN"

    return _normalize(hint) or "en-IN"


def _normalize(hint: str | None) -> str | None:
    if not hint or hint == "unknown":
        return None
    if "-" in hint:
        return hint
    # Sarvam sometimes returns short forms like "te"; map to BCP-47.
    short = hint.lower()
    for code, _, _ in _BLOCKS:
        if code.startswith(short + "-"):
            return code
    if short == "en":
        return "en-IN"
    return None
