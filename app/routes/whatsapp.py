from fastapi import APIRouter, Request, Response
from loguru import logger

from app.config import settings
from app.lib.verify import verify_twilio_signature

router = APIRouter(prefix="/twilio", tags=["twilio"])


def _twiml_reply(text: str) -> Response:
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f"<Response><Message>{text}</Message></Response>"
    )
    return Response(content=body, media_type="application/xml")


@router.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    form = dict(await request.form())
    signature = request.headers.get("X-Twilio-Signature", "")

    # Twilio uses the externally-visible URL (ngrok / caddy) for the signature.
    # Build it from the configured PUBLIC_BASE_URL so the validator matches.
    public_url = f"{settings.public_base_url.rstrip('/')}{request.url.path}"

    if settings.app_env != "dev":
        if not verify_twilio_signature(public_url, form, signature):
            logger.warning(f"Twilio signature invalid url={public_url}")
            return Response(status_code=403)

    from_ = form.get("From", "")
    body = form.get("Body", "")
    num_media = int(form.get("NumMedia", "0") or "0")

    logger.info(f"WA in from={from_} media={num_media} body={body!r}")

    if num_media > 0:
        media_url = form.get("MediaUrl0", "")
        media_type = form.get("MediaContentType0", "")
        return _twiml_reply(
            f"Got media ({media_type}). Voice handling coming next."
        )

    return _twiml_reply(f"Echo: {body}")
