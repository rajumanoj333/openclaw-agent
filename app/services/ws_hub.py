"""
In-process pub/sub for the chat UI WebSocket.

When any inbound or outbound message lands (WhatsApp text, voice transcript,
poster, etc.), routes call `publish(phone, event)`. The WebSocket route in
`routes/ws.py` subscribes per-phone and forwards events to connected clients.

Phase 3 will swap this for Redis pub/sub so multiple uvicorn workers can
share the bus. The public API (publish / subscribe) stays the same.
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any, Literal


Channel = Literal["whatsapp", "voice", "ui", "system"]
Direction = Literal["in", "out"]


@dataclass
class ChatEvent:
    phone: str
    channel: Channel
    direction: Direction
    body: str | None = None
    media_url: str | None = None
    lang: str | None = None
    kind: str = "message"          # message | status | task
    status: str | None = None      # for kind=status: "scraping" | "designing" | ...
    agent_slug: str | None = None  # which agent generated this (out) or
                                   # which agent the user addressed (in).
                                   # None for system status events.
    meta: dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)
_lock = asyncio.Lock()


async def publish(event: ChatEvent) -> None:
    """Fan out an event to every subscriber for this phone."""
    queues = list(_subscribers.get(event.phone, ()))
    for q in queues:
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass


async def subscribe(phone: str) -> asyncio.Queue:
    """Return a queue that receives every future event for `phone`."""
    q: asyncio.Queue = asyncio.Queue(maxsize=128)
    async with _lock:
        _subscribers[phone].add(q)
    return q


async def unsubscribe(phone: str, q: asyncio.Queue) -> None:
    async with _lock:
        if phone in _subscribers:
            _subscribers[phone].discard(q)
            if not _subscribers[phone]:
                _subscribers.pop(phone, None)


def fire(
    phone: str,
    *,
    channel: Channel,
    direction: Direction,
    body: str | None = None,
    media_url: str | None = None,
    lang: str | None = None,
    kind: str = "message",
    status: str | None = None,
    agent_slug: str | None = None,
    **meta: Any,
) -> None:
    """
    Sync convenience wrapper: schedule a publish without awaiting. Use from
    background tasks where awaiting feels noisy.
    """
    event = ChatEvent(
        phone=phone,
        channel=channel,
        direction=direction,
        body=body,
        media_url=media_url,
        lang=lang,
        kind=kind,
        status=status,
        agent_slug=agent_slug,
        meta=dict(meta),
    )
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(publish(event))
    except RuntimeError:
        # no running loop — nothing to do (tests, scripts)
        pass
