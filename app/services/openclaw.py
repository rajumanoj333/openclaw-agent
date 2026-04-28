import httpx
from loguru import logger

from app.config import settings


async def ask_openclaw(message: str, *, to: str | None = None, timeout: int = 90) -> str:
    """
    Send `message` to OpenClaw via the VM proxy and return the assistant's
    reply text. `to` (E.164) lets the gateway derive a per-user session.
    """
    url = f"{settings.openclaw_url.rstrip('/')}/agent"
    payload = {"message": message, "agent": "main", "timeout": timeout}
    if to:
        payload["to"] = to

    async with httpx.AsyncClient(timeout=timeout + 30) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

    reply = data.get("reply", "").strip()
    logger.info(f"openclaw reply ms={data.get('ms')} session={data.get('session_id')}")
    return reply or "(no reply)"
