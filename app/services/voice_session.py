"""
Tiny in-memory store for outbound-call TwiML state.

When we trigger an outbound callback, Twilio will GET our `/twilio/voice/say/{call_id}`
URL. By then the call SID is known, but we need to look up which reply audio
to play. Cache it here for ~10 minutes.

Production: replace with Redis (already running in docker-compose).
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock


@dataclass
class VoiceReply:
    audio_name: str | None  # filename in audio_store, or None for plain text
    fallback_text: str
    expires_at: float


_store: dict[str, VoiceReply] = {}
_lock = Lock()
_TTL_SECONDS = 10 * 60


def put(call_id: str, audio_name: str | None, fallback_text: str) -> None:
    with _lock:
        _store[call_id] = VoiceReply(
            audio_name=audio_name,
            fallback_text=fallback_text,
            expires_at=time.time() + _TTL_SECONDS,
        )
        _gc_locked()


def get(call_id: str) -> VoiceReply | None:
    with _lock:
        item = _store.get(call_id)
        if not item:
            return None
        if time.time() > item.expires_at:
            _store.pop(call_id, None)
            return None
        return item


def _gc_locked() -> None:
    now = time.time()
    expired = [k for k, v in _store.items() if v.expires_at < now]
    for k in expired:
        _store.pop(k, None)
