from fastapi import APIRouter, BackgroundTasks, Request, Response
from loguru import logger

from app.config import settings
from app.lib.verify import verify_twilio_signature
from app.services import audio_store, business_profile, ws_hub
from app.services.intent import classify as classify_intent
from app.services.lang_detect import detect_lang
from app.services.onboarding import run_onboarding
from app.services.openclaw import ask_openclaw
from app.services.poster import generate_poster
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


def _phone_only(to: str) -> str:
    return to.removeprefix("whatsapp:") if to.startswith("whatsapp:") else to


async def _send_reply(to: str, text: str, *, with_audio: bool, lang: str,
                      agent_slug: str | None = None) -> None:
    """Always sends text. If `with_audio`, also sends a TTS audio version."""
    phone = _phone_only(to)
    ws_hub.fire(phone, channel="whatsapp", direction="out",
                body=text[:1500], lang=lang, agent_slug=agent_slug)
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
    ws_hub.fire(e164, channel="system", direction="out", kind="status", status="scraping",
                body=f"Scraping {url}")
    send_whatsapp(from_, "🔎 Got it. Fetching your business info — this takes ~30 sec…")
    try:
        _, summary = await run_onboarding(e164, url)
    except Exception as e:
        logger.exception("onboarding failed")
        send_whatsapp(from_, f"Onboarding error: {e}")
        return
    ws_hub.fire(e164, channel="system", direction="out", kind="status", status="onboarding_done")
    send_whatsapp(from_, summary[:1500])


def _public_image_url(name: str) -> str:
    base = settings.public_base_url.rstrip("/")
    return f"{base}/audio/{name}"


async def _process_poster(from_: str, e164: str, brief: str) -> None:
    profile = business_profile.get(e164)
    ws_hub.fire(e164, channel="system", direction="out", kind="status",
                status="designing", body=brief)
    send_whatsapp(from_, "🎨 Designing your poster… (~20 sec)")
    try:
        image, mime = await generate_poster(brief, profile=profile)
    except Exception as e:
        logger.exception("poster generation failed")
        send_whatsapp(from_, f"Couldn't generate the poster: {e}")
        return

    ext = "png" if "png" in mime else ("jpg" if "jpeg" in mime else "png")
    name = audio_store.save(image, ext)
    url = _public_image_url(name)

    business_name = (profile.name if profile else None) or "your business"
    caption = f"🖼️ Poster for {business_name}\nReply with edits, or 'post' when ready."
    ws_hub.fire(e164, channel="whatsapp", direction="out",
                body=caption, media_url=url, kind="message",
                agent_slug="morpheus")
    try:
        send_whatsapp_media(from_, url, body=caption)
    except Exception:
        logger.exception("twilio media send failed")
        send_whatsapp(from_, f"Poster ready: {url}")


async def _process_text(from_: str, text: str, *, with_audio: bool = False,
                        lang: str = "en-IN",
                        force_agent: str | None = None) -> None:
    """
    Pipeline shared by WhatsApp, Voice, and Web WS:
      - WhatsApp/Voice: force_agent=None → intent classifier picks the agent.
      - Web (per-agent thread): force_agent="ritu" / "kiran" / ... bypasses
        the classifier so the user's explicit pick wins. Ritu's strict
        scope rules then handle anything beyond social media.
    """
    e164 = from_.removeprefix("whatsapp:") if from_.startswith("whatsapp:") else from_

    profile = business_profile.get(e164)
    urls_in_msg = find_urls(text)

    # Onboarding flow: URL detected and no confirmed profile → scrape.
    if urls_in_msg and (profile is None or not profile.confirmed):
        await _process_onboarding(from_, e164, urls_in_msg[0])
        return

    intent = classify_intent(text)
    logger.info(f"intent classified text={text!r} intent={intent} force_agent={force_agent}")

    # Confirm pending onboarding profile.
    if intent == "confirm" and profile is not None and not profile.confirmed:
        business_profile.confirm(e164)
        name = profile.name or "your business"
        send_whatsapp(from_, f"✅ Saved profile for {name}. You can ask me anything now.")
        return

    # Poster intent: generate a brand-aware marketing creative.
    # If user explicitly picked a non-Morpheus agent, skip this — that
    # agent should respond + decline if poster is out of their scope.
    if intent == "poster" and (force_agent is None or force_agent == "morpheus"):
        await _process_poster(from_, e164, text)
        return

    # Pick the agent. Force-agent (UI) wins; otherwise intent classifier.
    from app.services import agent_config
    from app.services.agents.registry import AGENT_REGISTRY, route_message

    cfg = agent_config.get(e164)
    enabled = cfg.enabled_agents if cfg else []

    if force_agent and force_agent in AGENT_REGISTRY:
        agent_slug = force_agent
        logger.info(f"force_agent → {agent_slug}")
    else:
        agent_slug = route_message(text, enabled)
        logger.info(f"routed message → agent={agent_slug}")

    try:
        reply = await ask_openclaw(
            text, phone=e164, agent_slug=agent_slug, timeout=240
        )
    except Exception as e:
        logger.exception("openclaw call failed")
        reply = f"Agent error: {e}"

    reply_lang = detect_lang(reply, hint=lang)
    await _send_reply(from_, reply, with_audio=with_audio, lang=reply_lang,
                      agent_slug=agent_slug)


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

    # broadcast inbound to UI subscribers
    ws_hub.fire(_phone_only(from_), channel="whatsapp", direction="in", body=body)

    background.add_task(_process_text, from_, body)
    return _twiml("Working on it…")
