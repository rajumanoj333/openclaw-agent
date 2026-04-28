from twilio.rest import Client
from loguru import logger

from app.config import settings


_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        _client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    return _client


def send_whatsapp(to: str, body: str) -> str:
    """
    Send a WhatsApp text message. `to` must include the `whatsapp:` prefix
    (e.g. "whatsapp:+916304530240"). Returns the Twilio message SID.
    """
    msg = get_client().messages.create(
        from_=settings.twilio_whatsapp_from,
        to=to,
        body=body,
    )
    logger.info(f"sent WhatsApp to={to} sid={msg.sid}")
    return msg.sid


def send_whatsapp_media(to: str, media_url: str, body: str | None = None) -> str:
    """
    Send a WhatsApp message with media attached. `media_url` must be a
    publicly-fetchable HTTPS URL (Twilio downloads it server-side).
    """
    kwargs = {
        "from_": settings.twilio_whatsapp_from,
        "to": to,
        "media_url": [media_url],
    }
    if body:
        kwargs["body"] = body
    msg = get_client().messages.create(**kwargs)
    logger.info(f"sent WhatsApp media to={to} sid={msg.sid} url={media_url}")
    return msg.sid
