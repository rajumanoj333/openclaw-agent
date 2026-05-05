from fastapi import APIRouter, BackgroundTasks, Request, Response
from loguru import logger

from app.config import settings
from app.lib.verify import verify_twilio_signature
from app.services import audio_store, business_profile
from app.services.lang_detect import detect_lang
from app.services.onboarding import run_onboarding
from app.services.openclaw import ask_openclaw
from app.services.scrape import find_urls
from app.services.stt import transcribe
from app.services.tts import synthesize
from app.services.twilio_client import send_whatsapp, send_whatsapp_media
from app.services.twilio_media import download_media

router = APIRouter(prefix="/twilio", tags=["twilio"])


def _twiml(text: str | None = None) -> Response:
    if text is None:
        body = '<?xml version="1.0" encoding="UTF-8"?><Response/>'
    else:
        safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        body = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f"<Response><Message>{safe}</Message></Response>"
        )
    return Response(content=body, media_type="application/xml")


def _public_audio_url(name: str) -> str:
    base = settings.public_base_url.rstrip("/")
    return f"{base}/audio/{name}"


async def _send_reply(to: str, text: str, *, with_audio: bool, lang: str) -> None:
    """Always sends text. If `with_audio`, also sends a TTS audio version."""
    try:
        send_whatsapp(to, text[:1500])
    except Exception:
        logger.exception("twilio text send failed")

    if not with_audio:
        return

    try:
        audio, _, ext, backend = await synthesize(text[:1200], lang)
        name = audio_store.save(audio, ext)
        media_url = _public_audio_url(name)
        send_whatsapp_media(to, media_url, body=f"🔊 voice: {backend} ({lang})")
    except Exception:
        logger.exception("tts/audio send failed")


async def _process_onboarding(from_: str, e164: str, url: str) -> None:
    send_whatsapp(from_, "🔎 Got it. Fetching your business info — this takes ~30 sec…")
    try:
        _, summary = await run_onboarding(e164, url)
    except Exception as e:
        logger.exception("onboarding failed")
        send_whatsapp(from_, f"Onboarding error: {e}")
        return
    send_whatsapp(from_, summary[:1500])


async def _process_text(from_: str, text: str, *, with_audio: bool = False,
                        lang: str = "en-IN") -> None:
    e164 = from_.removeprefix("whatsapp:") if from_.startswith("whatsapp:") else from_

    # Onboarding: if user sends a URL and we don't yet have a confirmed
    # profile for them, run scrape + extract instead of routing to OpenClaw.
    profile = business_profile.get(e164)
    urls_in_msg = find_urls(text)
    if urls_in_msg and (profile is None or not profile.confirmed):
        await _process_onboarding(from_, e164, urls_in_msg[0])
        return

    # Confirm step: user replies "yes" to confirm an unconfirmed profile.
    if (
        profile is not None
        and not profile.confirmed
        and text.strip().lower() in {"yes", "y", "confirm", "ok", "okay", "ఔను", "हाँ"}
    ):
        business_profile.confirm(e164)
        name = profile.name or "your business"
        send_whatsapp(from_, f"✅ Saved profile for {name}. You can ask me anything now.")
        return

    try:
        reply = await ask_openclaw(text, to=e164, timeout=120)
    except Exception as e:
        logger.exception("openclaw call failed")
        reply = f"Agent error: {e}"

    reply_lang = detect_lang(reply, hint=lang)
    await _send_reply(from_, reply, with_audio=with_audio, lang=reply_lang)


async def _process_voice_note(from_: str, media_url: str, mime: str) -> None:
    try:
        audio, content_type = await download_media(media_url)
    except Exception as e:
        logger.exception("media download failed")
        send_whatsapp(from_, f"Could not fetch your audio: {e}")
        return

    actual_mime = content_type or mime or "audio/ogg"
    try:
        text, raw_lang = await transcribe(audio, actual_mime)
    except Exception as e:
        logger.exception("stt failed")
        send_whatsapp(from_, f"Could not transcribe your audio: {e}")
        return

    if not text.strip():
        send_whatsapp(from_, "I couldn't make out the audio. Please try again or send text.")
        return

    lang = detect_lang(text, hint=raw_lang)
    logger.info(f"voice transcript lang={lang} (raw={raw_lang}) text={text!r}")
    send_whatsapp(from_, f"🎙️ I heard: \"{text}\" ({lang})\nWorking on it…")
    await _process_text(from_, text, with_audio=True, lang=lang)


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
        media_url = form.get("MediaUrl0", "")
        mime = form.get("MediaContentType0", "")
        if mime.startswith("audio/") or mime.startswith("video/"):
            background.add_task(_process_voice_note, from_, media_url, mime)
            return _twiml("Got your voice note. Transcribing…")
        return _twiml(f"Got media ({mime}). Only voice notes supported for now.")

    if not body.strip():
        return _twiml("Send me a message and I will get on it.")

    background.add_task(_process_text, from_, body)
    return _twiml("Working on it…")
