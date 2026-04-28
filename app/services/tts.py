"""
Text-to-speech routing.

Sarvam handles Indic languages with native voices; Google handles English
with neural voices. Returns (audio_bytes, mime, file_extension).

Sarvam REST API splits long text into chunks and returns base64-encoded
WAV per chunk in the `audios` array. We concatenate to one WAV.
"""
from __future__ import annotations

import asyncio
import base64
import io
from pathlib import Path
from typing import Literal

import httpx
from loguru import logger

from app.config import settings

Backend = Literal["sarvam", "google"]

_SARVAM_LANGS = {
    "hi-IN", "te-IN", "ta-IN", "kn-IN", "ml-IN",
    "bn-IN", "gu-IN", "pa-IN", "or-IN", "mr-IN",
}
_DEFAULT_SARVAM_SPEAKER = "anushka"

# WhatsApp accepts: audio/aac, audio/mp4, audio/amr, audio/mpeg, audio/ogg.
# Both Sarvam (WAV) and Google (MP3) outputs are not all directly accepted,
# so we use MP3 for Google and OGG/WAV for Sarvam — adjust if WhatsApp rejects.


async def synthesize(text: str, lang_code: str) -> tuple[bytes, str, str]:
    """
    Returns (audio_bytes, mime_type, file_extension). Picks Sarvam for Indic
    languages, Google otherwise.
    """
    text = (text or "").strip()
    if not text:
        raise ValueError("synthesize: empty text")

    if lang_code in _SARVAM_LANGS and settings.sarvam_key:
        try:
            return await _sarvam_tts(text, lang_code)
        except Exception as e:
            logger.warning(f"sarvam tts failed lang={lang_code}: {e!r}; trying google")

    return await _google_tts(text, lang_code)


async def _sarvam_tts(text: str, lang_code: str) -> tuple[bytes, str, str]:
    url = f"{settings.sarvam_base_url.rstrip('/')}/text-to-speech"
    headers = {"api-subscription-key": settings.sarvam_key}
    body = {
        "text": text[:1500],
        "target_language_code": lang_code,
        "speaker": _DEFAULT_SARVAM_SPEAKER,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, json=body, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    audios = data.get("audios") or []
    if not audios:
        raise RuntimeError(f"sarvam tts returned no audios: {data}")

    chunks = [base64.b64decode(a) for a in audios]
    wav = chunks[0] if len(chunks) == 1 else _concat_wav(chunks)

    # WhatsApp rejects audio/wav. Convert to MP3 via pydub (needs ffmpeg).
    mp3 = await asyncio.to_thread(_wav_to_mp3, wav)
    logger.info(
        f"sarvam tts lang={lang_code} wav={len(wav)} mp3={len(mp3)} chunks={len(chunks)}"
    )
    return mp3, "audio/mpeg", "mp3"


def _wav_to_mp3(wav_bytes: bytes) -> bytes:
    """Convert WAV bytes to MP3 bytes via pydub (requires ffmpeg in PATH)."""
    from pydub import AudioSegment

    seg = AudioSegment.from_file(io.BytesIO(wav_bytes), format="wav")
    out = io.BytesIO()
    # WhatsApp audio bitrate ~64-96 kbps is plenty for speech
    seg.export(out, format="mp3", bitrate="96k")
    return out.getvalue()


def _concat_wav(chunks: list[bytes]) -> bytes:
    """
    Naive WAV concat: keep header from first chunk, strip RIFF headers
    from subsequent chunks, fix the data length field. Each Sarvam chunk
    is a 16-bit PCM mono/stereo WAV with a standard 44-byte header.
    """
    if not chunks:
        return b""
    if len(chunks) == 1:
        return chunks[0]

    header = chunks[0][:44]
    pcm = chunks[0][44:] + b"".join(c[44:] for c in chunks[1:])
    # patch RIFF chunk size (bytes 4-7) and data subchunk size (bytes 40-43)
    riff_size = (36 + len(pcm)).to_bytes(4, "little")
    data_size = len(pcm).to_bytes(4, "little")
    return header[:4] + riff_size + header[8:40] + data_size + pcm


async def _google_tts(text: str, lang_code: str) -> tuple[bytes, str, str]:
    if not Path(settings.google_application_credentials).exists():
        raise RuntimeError(
            f"google credentials not found: {settings.google_application_credentials}"
        )

    from google.cloud import texttospeech

    def _run() -> bytes:
        client = texttospeech.TextToSpeechClient.from_service_account_file(
            settings.google_application_credentials
        )
        synthesis_input = texttospeech.SynthesisInput(text=text[:2000])
        voice = texttospeech.VoiceSelectionParams(
            language_code=lang_code,
            ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL,
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=1.0,
        )
        resp = client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )
        return resp.audio_content

    audio = await asyncio.to_thread(_run)
    logger.info(f"google tts lang={lang_code} bytes={len(audio)}")
    return audio, "audio/mpeg", "mp3"
