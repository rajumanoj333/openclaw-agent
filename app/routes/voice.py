"""
Twilio voice call routes — Flow A (async callback).

Inbound flow:
    Caller → /twilio/voice          (greet + start record)
    Recording done → /twilio/voice/recorded
    Background: STT → WhatsApp confirm → OpenClaw → outbound callback

Outbound flow:
    /twilio/voice/say/{call_id}     served when Twilio dials user back;
                                    plays the cached reply audio + hangs up.
"""
from __future__ import annotations

import secrets

from fastapi import APIRouter, BackgroundTasks, Form, HTTPException, Request, Response
from loguru import logger

from app.config import settings
from app.services import audio_store, voice_session
from app.services.lang_detect import detect_lang
from app.services.openclaw import ask_openclaw
from app.services.stt import transcribe
from app.services.tts import synthesize
from app.services.twilio_client import make_call, send_whatsapp
from app.services.twilio_media import download_media

router = APIRouter(prefix="/twilio/voice", tags=["twilio-voice"])

GREETING = "Hello, this is Morpheus. What can I do for you? Please speak after the beep, then stay silent."
RECORD_FOOTER = "Thanks. I will work on it and call you back when it is done."
GOODBYE = "Sorry, I didn't catch that. Goodbye."


def _twiml(xml_body: str) -> Response:
    return Response(
        content=f'<?xml version="1.0" encoding="UTF-8"?><Response>{xml_body}</Response>',
        media_type="application/xml",
    )


def _public_url(path: str) -> str:
    return f"{settings.public_base_url.rstrip('/')}{path}"


@router.post("")
async def voice_inbound(request: Request):
    """
    Twilio hits this when someone dials the voice number.
    Greets the caller and begins a 60s recording.
    """
    form = dict(await request.form())
    logger.info(
        f"voice inbound from={form.get('From')} to={form.get('To')} "
        f"sid={form.get('CallSid')}"
    )

    # action URL is where Twilio POSTs the recording metadata when done.
    action = _public_url("/twilio/voice/recorded")
    body = (
        f'<Say voice="alice">{GREETING}</Say>'
        f'<Record action="{action}" method="POST" '
        f'maxLength="60" timeout="3" playBeep="true" trim="trim-silence" '
        f'finishOnKey="#" />'
        f'<Say voice="alice">{GOODBYE}</Say>'
    )
    return _twiml(body)


@router.post("/recorded")
async def voice_recorded(
    request: Request,
    background: BackgroundTasks,
    From: str = Form(""),
    To: str = Form(""),
    CallSid: str = Form(""),
    RecordingUrl: str = Form(""),
    RecordingSid: str = Form(""),
    RecordingDuration: str = Form("0"),
):
    """
    Twilio POSTs here after the caller stops recording. We acknowledge with
    a short TwiML, then hang up and process the recording in the background.
    """
    logger.info(
        f"voice recorded from={From} sid={CallSid} duration={RecordingDuration}s "
        f"url={RecordingUrl}"
    )

    if not RecordingUrl:
        return _twiml(f'<Say voice="alice">{GOODBYE}</Say><Hangup/>')

    background.add_task(
        _process_voice_call,
        caller=From,
        recording_url=RecordingUrl,
    )

    body = f'<Say voice="alice">{RECORD_FOOTER}</Say><Hangup/>'
    return _twiml(body)


@router.api_route("/say/{call_id}", methods=["GET", "POST"])
async def voice_say(call_id: str):
    """
    TwiML served when Twilio dials the user back. Plays the cached reply.
    """
    item = voice_session.get(call_id)
    if not item:
        body = '<Say voice="alice">No reply cached. Goodbye.</Say><Hangup/>'
        return _twiml(body)

    if item.audio_name:
        audio_url = _public_url(f"/audio/{item.audio_name}")
        body = f'<Play>{audio_url}</Play><Hangup/>'
    else:
        # fallback to Twilio TTS if our TTS failed earlier
        safe = item.fallback_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        body = f'<Say voice="alice">{safe[:1500]}</Say><Hangup/>'
    return _twiml(body)


async def _process_voice_call(caller: str, recording_url: str) -> None:
    """
    1. Download recording (Twilio adds .mp3 to the URL).
    2. STT transcribe.
    3. WhatsApp confirmation.
    4. Send to OpenClaw.
    5. Generate TTS audio of reply.
    6. Outbound call back to caller; TwiML plays the audio.
    7. Send WhatsApp text reply.
    """
    wa_to = settings.whatsapp_notify_to.strip() or (
        caller if caller.startswith("whatsapp:") else f"whatsapp:{caller}"
    )

    # Twilio recording requires `.mp3` suffix to fetch as MP3 instead of WAV
    audio_url = recording_url + ".mp3"
    try:
        audio_bytes, content_type = await download_media(audio_url)
    except Exception as e:
        logger.exception("voice recording download failed")
        try:
            send_whatsapp(wa_to, f"Could not fetch your voice recording: {e}")
        except Exception:
            pass
        return

    try:
        transcript, raw_lang = await transcribe(audio_bytes, content_type or "audio/mpeg")
    except Exception as e:
        logger.exception("voice STT failed")
        try:
            send_whatsapp(wa_to, f"Could not transcribe your call: {e}")
        except Exception:
            pass
        return

    if not transcript.strip():
        try:
            send_whatsapp(wa_to, "I couldn't understand your call. Please try again.")
        except Exception:
            pass
        return

    lang = detect_lang(transcript, hint=raw_lang)
    logger.info(f"voice call transcript lang={lang} text={transcript!r}")

    try:
        send_whatsapp(
            wa_to,
            f"📞 Got your call. I heard: \"{transcript}\" ({lang})\nWorking on it…",
        )
    except Exception:
        logger.exception("twilio WA confirm send failed")

    # Run task via OpenClaw — keyed off caller phone for session memory
    try:
        reply = await ask_openclaw(transcript, to=caller, timeout=180)
    except Exception as e:
        logger.exception("openclaw call failed")
        reply = f"I ran into an error: {e}"

    reply_lang = detect_lang(reply, hint=lang)

    # Generate TTS of the reply
    audio_name: str | None = None
    try:
        audio, _, ext, backend = await synthesize(reply[:1200], reply_lang)
        audio_name = audio_store.save(audio, ext)
        logger.info(f"voice reply tts backend={backend} lang={reply_lang} file={audio_name}")
    except Exception:
        logger.exception("voice reply TTS failed; will fall back to Twilio Say")

    # Cache reply for the TwiML URL Twilio will fetch on outbound call
    call_id = secrets.token_urlsafe(12)
    voice_session.put(call_id, audio_name, reply)

    try:
        twiml_url = _public_url(f"/twilio/voice/say/{call_id}")
        make_call(caller, twiml_url)
    except Exception:
        logger.exception("outbound call failed")

    # Always send WhatsApp text version as well
    try:
        send_whatsapp(wa_to, f"📞 Result:\n{reply[:1400]}")
    except Exception:
        logger.exception("twilio WA result send failed")
