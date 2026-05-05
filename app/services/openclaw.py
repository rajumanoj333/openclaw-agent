import httpx
from loguru import logger

from app.config import settings


def _wrap_with_persona(message: str, phone: str | None) -> str:
    """
    Prepend the per-user agent persona (when defined) before the user
    message so OpenClaw stays in-scope. Lazy import avoids circular deps.
    """
    if not phone:
        return message
    try:
        from app.services import agent_config, business_profile
    except Exception:
        return message

    business = business_profile.get(phone)
    biz_name = business.name if business else None
    prefix = agent_config.build_persona_prefix(phone, business_name=biz_name)
    if not prefix:
        return message
    return f"{prefix}\n\n--- USER MESSAGE ---\n{message}"


async def ask_openclaw(message: str, *, to: str | None = None, timeout: int = 240) -> str:
    """
    Send `message` to OpenClaw via the VM proxy and return the assistant's
    reply text. `to` (E.164) lets the gateway derive a per-user session.
    """
    url = f"{settings.openclaw_url.rstrip('/')}/agent"
    wrapped = _wrap_with_persona(message, phone=to)

    payload = {"message": wrapped, "agent": "main", "timeout": timeout}
    if to:
        payload["to"] = to

    async with httpx.AsyncClient(timeout=timeout + 30) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

    reply = data.get("reply", "").strip()
    logger.info(f"openclaw reply ms={data.get('ms')} session={data.get('session_id')}")
    return reply or "(no reply)"
