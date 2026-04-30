"""
Pre-generated voice prompts for the voice-call flow.

Twilio's built-in `<Say>` voices sound robotic and don't pronounce Indic
text well. We generate every prompt once with Sarvam TTS at app startup,
cache the MP3s on disk, and `<Play>` them during calls. Zero mid-call TTS
latency, natural voices in both languages.
"""
from __future__ import annotations

from pathlib import Path

from loguru import logger

from app.config import settings
from app.services.tts import synthesize

# Same naming convention regardless of language so route lookup is trivial.
PROMPTS: dict[str, dict[str, str]] = {
    # Bilingual greeting in English — most callers understand "press 1 / press 2".
    "greeting": {
        "text": (
            "Hello, this is Morpheus, your AI assistant. "
            "Press 1 to continue in English. "
            "Press 2 to continue in Telugu."
        ),
        "lang": "en-IN",
    },
    "prompt_en": {
        "text": "Please speak your request after the beep, then stay silent.",
        "lang": "en-IN",
    },
    "prompt_te": {
        "text": "దయచేసి బీప్ తరువాత మీ request చెప్పండి, ఆపై మౌనంగా ఉండండి.",
        "lang": "te-IN",
    },
    "footer_en": {
        "text": "Thanks. I will work on it and call you back when it is done.",
        "lang": "en-IN",
    },
    "footer_te": {
        "text": "ధన్యవాదాలు. నేను దాని మీద పని చేసి, అయిపోయాక మీకు తిరిగి call చేస్తాను.",
        "lang": "te-IN",
    },
    "goodbye_en": {
        "text": "Sorry, I did not catch that. Goodbye.",
        "lang": "en-IN",
    },
    "goodbye_te": {
        "text": "క్షమించండి, నాకు అర్థం కాలేదు. వీడ్కోలు.",
        "lang": "te-IN",
    },
    "no_selection": {
        "text": (
            "Sorry, no selection was received. Press 1 for English. "
            "Press 2 for Telugu."
        ),
        "lang": "en-IN",
    },
}

STATIC_DIR = Path(__file__).resolve().parents[2] / "data" / "audio_static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)


def path_for(name: str) -> Path:
    """Return the on-disk path of a static prompt MP3."""
    return STATIC_DIR / f"{name}.mp3"


def url_for(name: str) -> str:
    """Public URL Twilio fetches when we say `<Play>...</Play>`."""
    base = settings.public_base_url.rstrip("/")
    return f"{base}/audio/static/{name}.mp3"


async def ensure_all() -> None:
    """
    Generate any missing prompt files. Called once on app startup.
    Idempotent: if all files exist, no API calls happen.
    """
    missing: list[str] = []
    for key in PROMPTS:
        if not path_for(key).exists():
            missing.append(key)

    if not missing:
        logger.info(f"voice prompts cache hit ({len(PROMPTS)} files in {STATIC_DIR})")
        return

    logger.info(f"voice prompts generating: {missing}")
    for key in missing:
        cfg = PROMPTS[key]
        try:
            audio, _, _, backend = await synthesize(cfg["text"], cfg["lang"])
        except Exception:
            logger.exception(f"voice prompt failed: {key}")
            continue
        path_for(key).write_bytes(audio)
        logger.info(
            f"voice prompt saved key={key} backend={backend} "
            f"lang={cfg['lang']} bytes={len(audio)}"
        )


async def regenerate(name: str) -> bool:
    """Force regeneration of a single prompt (e.g. after editing text)."""
    cfg = PROMPTS.get(name)
    if not cfg:
        return False
    try:
        audio, _, _, backend = await synthesize(cfg["text"], cfg["lang"])
    except Exception:
        logger.exception(f"voice prompt regen failed: {name}")
        return False
    path_for(name).write_bytes(audio)
    logger.info(f"voice prompt regenerated key={name} backend={backend}")
    return True
