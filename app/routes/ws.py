"""
WebSocket endpoint for the chat UI.

Client connects to:    ws://host/ws/{phone}
On connect we subscribe to the in-process pub/sub bus and forward every
ChatEvent for that phone as JSON. Client can send text frames {type: "msg",
body: "..."} which we route through the same pipeline as a WhatsApp text.
"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from app.services import ws_hub
from app.services.ws_hub import ChatEvent

router = APIRouter(tags=["ws"])


@router.websocket("/ws/{phone}")
async def chat_ws(websocket: WebSocket, phone: str):
    await websocket.accept()
    queue = await ws_hub.subscribe(phone)
    logger.info(f"ws connect phone={phone}")

    sender_task = asyncio.create_task(_pump_to_client(websocket, queue))
    try:
        while True:
            text = await websocket.receive_text()
            await _handle_inbound(phone, text)
    except WebSocketDisconnect:
        logger.info(f"ws disconnect phone={phone}")
    except Exception:
        logger.exception(f"ws error phone={phone}")
    finally:
        sender_task.cancel()
        await ws_hub.unsubscribe(phone, queue)


async def _pump_to_client(ws: WebSocket, queue: asyncio.Queue) -> None:
    try:
        while True:
            event: ChatEvent = await queue.get()
            await ws.send_text(json.dumps(event.to_dict(), default=str))
    except asyncio.CancelledError:
        return
    except Exception:
        logger.exception("ws pump error")


async def _handle_inbound(phone: str, raw: str) -> None:
    """
    Route messages typed in the UI through the same handler the WhatsApp
    webhook uses. Lazy import to avoid circular import at boot.
    """
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = {"type": "msg", "body": raw}

    if payload.get("type") != "msg":
        return
    body = (payload.get("body") or "").strip()
    if not body:
        return

    # NOTE: do NOT echo this back via ws_hub. The composer paints the user's
    # own message optimistically, and broadcasting would double it on each
    # connected client. Backend only broadcasts agent replies + status.

    # Run through the same pipeline as WhatsApp text. Use a fake "whatsapp:"
    # prefix so the existing handler can extract an E.164 cleanly.
    from app.routes.whatsapp import _process_text

    asyncio.create_task(
        _process_text(f"whatsapp:{phone}", body, with_audio=False, lang="en-IN")
    )
