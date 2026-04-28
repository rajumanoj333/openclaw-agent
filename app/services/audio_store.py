"""
Disk-backed audio cache. Twilio fetches the file via the public ngrok URL,
so we keep generated audio on disk for a short TTL and clean expired files
on each new write.
"""
from __future__ import annotations

import time
import uuid
from pathlib import Path

from loguru import logger

_AUDIO_DIR = Path(__file__).resolve().parents[2] / "data" / "audio"
_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
_TTL_SECONDS = 30 * 60  # 30 minutes — Twilio fetch usually within seconds


def save(audio: bytes, ext: str) -> str:
    """Returns the public-facing filename (no path)."""
    name = f"{uuid.uuid4().hex}.{ext}"
    path = _AUDIO_DIR / name
    path.write_bytes(audio)
    _gc()
    return name


def path_for(name: str) -> Path:
    return _AUDIO_DIR / name


def _gc() -> None:
    cutoff = time.time() - _TTL_SECONDS
    removed = 0
    for f in _AUDIO_DIR.iterdir():
        try:
            if f.is_file() and f.stat().st_mtime < cutoff:
                f.unlink()
                removed += 1
        except OSError:
            continue
    if removed:
        logger.info(f"audio_store gc removed={removed}")
