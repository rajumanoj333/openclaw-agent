"""
Speech-to-text routing.

Sarvam saarika auto-detects English + Indic languages in one call, so it
serves as the primary backend. Google Cloud Speech is the fallback when
Sarvam errors out or returns an empty transcript.
"""
from __future__ import annotations

import asyncio
import os
from typing import Literal

import httpx
from loguru import logger

from app.config import settings

Backend = Literal["sarvam", "google", "auto"]

# Map Twilio MIME types to Google Speech encodings.
_GOOGLE_ENCODING = {
    "audio/ogg": "OGG_OPUS",
    "audio/ogg; codecs=opus": "OGG_OPUS",
    "audio/opus": "OGG_OPUS",
    "audio/wav": "LINEAR16",
    "audio/x-wav": "LINEAR16",
    "audio/mpeg": "MP3",
    "audio/mp3": "MP3",
    "audio/amr": "AMR",
    "audio/3gpp": "AMR",
}


async def transcribe(audio: bytes, mime: str, *, prefer: Backend = "auto") -> tuple[str, str]:
    """
    Returns (text, language_code). language_code follows BCP-47 (e.g. "en-IN", "te-IN").
    """
    if prefer == "google":
        return await _google_stt(audio, mime)

    if settings.sarvam_key:
        try:
            text, lang = await _sarvam_stt(audio, mime)
            if text.strip():
                return text, lang
            logger.warning("sarvam returned empty transcript; trying google")
        except Exception as e:
            logger.warning(f"sarvam STT failed: {e!r}; trying google")

    return await _google_stt(audio, mime)


async def _sarvam_stt(audio: bytes, mime: str) -> tuple[str, str]:
    """
    Sarvam Speech-to-Text using saaras:v3 (auto language detection across
    Indian languages + English). REST endpoint accepts ≤30s audio per call;
    longer clips need the batch API.
    Doc: https://docs.sarvam.ai/api-reference-docs/speech-to-text/apis/rest-api
    """
    url = f"{settings.sarvam_base_url.rstrip('/')}/speech-to-text"
    suffix = _ext_for_mime(mime)
    files = {"file": (f"audio.{suffix}", audio, mime or "application/octet-stream")}
    # mode=codemix handles natural Hindi/Telugu+English mixing; falls back to
    # straight transcription when speech is monolingual.
    data = {"model": "saaras:v3", "mode": "codemix"}
    headers = {"api-subscription-key": settings.sarvam_key}

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, files=files, data=data, headers=headers)
        resp.raise_for_status()
        body = resp.json()

    text = (body.get("transcript") or "").strip()
    lang = body.get("language_code") or "unknown"
    logger.info(f"sarvam stt lang={lang} chars={len(text)}")
    return text, lang


async def _google_stt(audio: bytes, mime: str) -> tuple[str, str]:
    """
    Google Cloud Speech-to-Text. Tries en-IN with te-IN/hi-IN as alternates.
    """
    if not os.path.exists(settings.google_application_credentials):
        raise RuntimeError(
            f"GOOGLE_APPLICATION_CREDENTIALS file not found: "
            f"{settings.google_application_credentials}"
        )

    # Lazy import so the app boots even when google deps aren't ready
    from google.cloud import speech

    def _run() -> tuple[str, str]:
        client = speech.SpeechClient.from_service_account_file(
            settings.google_application_credentials
        )
        encoding = _GOOGLE_ENCODING.get(
            mime.split(";")[0].strip().lower(), speech.RecognitionConfig.AudioEncoding.ENCODING_UNSPECIFIED
        )
        config = speech.RecognitionConfig(
            encoding=encoding if isinstance(encoding, int) else getattr(
                speech.RecognitionConfig.AudioEncoding, encoding
            ),
            language_code="en-IN",
            alternative_language_codes=["te-IN", "hi-IN"],
            enable_automatic_punctuation=True,
            model="default",
        )
        rec_audio = speech.RecognitionAudio(content=audio)
        resp = client.recognize(config=config, audio=rec_audio)
        if not resp.results:
            return "", "unknown"
        result = resp.results[0]
        text = result.alternatives[0].transcript if result.alternatives else ""
        lang = getattr(result, "language_code", None) or "en-IN"
        return text.strip(), lang

    text, lang = await asyncio.to_thread(_run)
    logger.info(f"google stt lang={lang} chars={len(text)}")
    return text, lang


def _ext_for_mime(mime: str) -> str:
    base = (mime or "").split(";")[0].strip().lower()
    if base.startswith("audio/ogg"):
        return "ogg"
    if base in {"audio/wav", "audio/x-wav"}:
        return "wav"
    if base in {"audio/mpeg", "audio/mp3"}:
        return "mp3"
    if base == "audio/amr":
        return "amr"
    if base == "audio/opus":
        return "opus"
    return "bin"
