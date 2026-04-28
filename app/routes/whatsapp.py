from fastapi import APIRouter, BackgroundTasks, Request, Response
from loguru import logger

from app.config import settings
from app.lib.verify import verify_twilio_signature
from app.services.openclaw import ask_openclaw
from app.services.twilio_client import send_whatsapp

router = APIRouter(prefix="/twilio", tags=["twilio"])


def _twiml(text: str | None = None) -> Response:
    if text is None:
        body = '<?xml version="1.0" encoding="UTF-8"?><Response/>'
    else:
        # Escape XML-special chars cheaply
        safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        body = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f"<Response><Message>{safe}</Message></Response>"
        )
    return Response(content=body, media_type="application/xml")


async def _process_and_reply(from_: str, text: str) -> None:
    e164 = from_.removeprefix("whatsapp:") if from_.startswith("whatsapp:") else from_
    try:
        reply = await ask_openclaw(text, to=e164, timeout=120)
    except Exception as e:
        logger.exception("openclaw call failed")
        reply = f"Agent error: {e}"

    try:
        send_whatsapp(from_, reply[:1500])
    except Exception:
        logger.exception("twilio send failed")


@router.post("/whatsapp")
async def whatsapp_webhook(request: Request, background: BackgroundTasks):
    form = dict(await request.form())
    signature = request.headers.get("X-Twilio-Signature", "")

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
        return _twiml("Got media. Voice handling coming next.")

    if not body.strip():
        return _twiml("Send me a message and I will get on it.")

    # Twilio webhook must reply within 15s. OpenClaw can take ~20s.
    # Ack immediately and push the real answer via REST.
    background.add_task(_process_and_reply, from_, body)
    return _twiml("Working on it…")
