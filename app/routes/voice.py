"""
Twilio voice call routes — bilingual Flow A.

Flow:
    POST /twilio/voice                  greet + gather digit (1=en, 2=te)
    POST /twilio/voice/lang             read digit, play prompt, start record
    POST /twilio/voice/recorded         after caller stops; ack + bg process
    GET  /twilio/voice/say/{call_id}    TwiML served on outbound callback

Every spoken line uses Sarvam-generated MP3s served from /audio/static/.
"""
from __future__ import annotations

import secrets

from fastapi import APIRouter, BackgroundTasks, Form, Request, Response
from loguru import logger

from app.config import settings
from app.services import audio_store, voice_prompts, voice_session, ws_hub
from app.services.lang_detect import detect_lang
from app.services.openclaw import ask_openclaw
from app.services.stt import transcribe
from app.services.tts import synthesize
from app.services.twilio_client import make_call, send_whatsapp
from app.services.twilio_media import download_media

router = APIRouter(prefix="/twilio/voice", tags=["twilio-voice"])

LANG_BY_DIGIT = {"1": "en-IN", "2": "te-IN"}
PROMPT_BY_LANG = {"en-IN": "prompt_en", "te-IN": "prompt_te"}
FOOTER_BY_LANG = {"en-IN": "footer_en", "te-IN": "footer_te"}
GOODBYE_BY_LANG = {"en-IN": "goodbye_en", "te-IN": "goodbye_te"}


def _twiml(xml_body: str) -> Response:
    return Response(
        content=f'<?xml version="1.0" encoding="UTF-8"?><Response>{xml_body}</Response>',
        media_type="application/xml",
    )


def _public_url(path: str) -> str:
    return f"{settings.public_base_url.rstrip('/')}{path}"


def _play(prompt_name: str) -> str:
    return f"<Play>{voice_prompts.url_for(prompt_name)}</Play>"


@router.post("")
async def voice_inbound(request: Request):
    """
    Twilio hits this when someone dials the voice number.
    Plays the bilingual greeting and gathers a single DTMF digit.
    """
    form = dict(await request.form())
    logger.info(
        f"voice inbound from={form.get('From')} to={form.get('To')} "
        f"sid={form.get('CallSid')}"
    )

    action = _public_url("/twilio/voice/lang")
    body = (
        f'<Gather numDigits="1" timeout="6" method="POST" action="{action}">'
        f"{_play('greeting')}"
        f"</Gather>"
        # If no digit pressed, replay greeting once then hang up.
        f"{_play('no_selection')}"
        f"<Hangup/>"
    )
    return _twiml(body)


@router.post("/lang")
async def voice_lang(
    request: Request,
    Digits: str = Form(""),
    From: str = Form(""),
    CallSid: str = Form(""),
):
    """
    Twilio POSTs the digit the caller pressed. Pick language and start
    recording with the language-appropriate prompt.
    """
    lang = LANG_BY_DIGIT.get(Digits.strip())
    logger.info(f"voice lang from={From} sid={CallSid} digit={Digits!r} lang={lang}")

    if lang is None:
        # Unrecognized digit — replay greeting + gather once more
        action = _public_url("/twilio/voice/lang")
        body = (
            f"{_play('no_selection')}"
            f'<Gather numDigits="1" timeout="6" method="POST" action="{action}">'
            f"{_play('greeting')}"
            f"</Gather>"
            f"<Hangup/>"
        )
        return _twiml(body)

    record_action = _public_url(f"/twilio/voice/recorded?lang={lang}")
    body = (
        f"{_play(PROMPT_BY_LANG[lang])}"
        f'<Record action="{record_action}" method="POST" '
        f'maxLength="60" timeout="3" playBeep="true" '
        f'trim="trim-silence" finishOnKey="#" />'
        f"{_play(GOODBYE_BY_LANG[lang])}"
        f"<Hangup/>"
    )
    return _twiml(body)


@router.post("/recorded")
async def voice_recorded(
    request: Request,
    background: BackgroundTasks,
    From: str = Form(""),
    CallSid: str = Form(""),
    RecordingUrl: str = Form(""),
    RecordingDuration: str = Form("0"),
):
    """
    Twilio POSTs after the caller stops recording. Ack with the localized
    "I'll call back" footer, hang up, and process in the background.
    """
    lang = request.query_params.get("lang", "en-IN")
    logger.info(
        f"voice recorded from={From} sid={CallSid} lang={lang} "
        f"duration={RecordingDuration}s url={RecordingUrl}"
    )

    if not RecordingUrl:
        body = f"{_play(GOODBYE_BY_LANG.get(lang, 'goodbye_en'))}<Hangup/>"
        return _twiml(body)

    background.add_task(
        _process_voice_call,
        caller=From,
        recording_url=RecordingUrl,
        lang=lang,
    )

    footer = FOOTER_BY_LANG.get(lang, "footer_en")
    body = f"{_play(footer)}<Hangup/>"
    return _twiml(body)


@router.api_route("/say/{call_id}", methods=["GET", "POST"])
async def voice_say(call_id: str):
    """TwiML served when Twilio dials the user back. Plays the cached reply."""
    item = voice_session.get(call_id)
    if not item:
        body = f"{_play('goodbye_en')}<Hangup/>"
        return _twiml(body)

    if item.audio_name:
        audio_url = _public_url(f"/audio/{item.audio_name}")
        body = f"<Play>{audio_url}</Play><Hangup/>"
    else:
        # If TTS failed earlier we have only text. Better to still try
        # synthesizing a short fallback than use Twilio's robotic voice.
        safe = item.fallback_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        body = f'<Say voice="alice">{safe[:1500]}</Say><Hangup/>'
    return _twiml(body)


async def _process_voice_call(caller: str, recording_url: str, lang: str) -> None:
    """
    1. Download recording.
    2. STT (lang hint from caller's selection).
    3. WhatsApp confirmation.
    4. Send to OpenClaw.
    5. Generate TTS audio of reply in the same language.
    6. Outbound call back; TwiML plays the audio.
    7. Send WhatsApp text reply.
    """
    wa_to = settings.whatsapp_notify_to.strip() or (
        caller if caller.startswith("whatsapp:") else f"whatsapp:{caller}"
    )

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

    # Caller chose the language; honor that even if the transcript scripts
    # leak through (e.g. someone says English numbers in a Telugu sentence).
    final_lang = lang or detect_lang(transcript, hint=raw_lang)
    logger.info(
        f"voice call transcript caller_lang={lang} stt_lang={raw_lang} "
        f"final={final_lang} text={transcript!r}"
    )

    # Broadcast voice transcript to UI subscribers
    ws_hub.fire(caller, channel="voice", direction="in",
                body=transcript, lang=final_lang)

    try:
        send_whatsapp(
            wa_to,
            f"📞 Got your call. I heard: \"{transcript}\" ({final_lang})\nWorking on it…",
        )
    except Exception:
        logger.exception("twilio WA confirm send failed")

    try:
        reply = await ask_openclaw(transcript, to=caller, timeout=180)
    except Exception as e:
        logger.exception("openclaw call failed")
        reply = f"I ran into an error: {e}"

    audio_name: str | None = None
    try:
        audio, _, ext, backend = await synthesize(reply[:1200], final_lang)
        audio_name = audio_store.save(audio, ext)
        logger.info(
            f"voice reply tts backend={backend} lang={final_lang} file={audio_name}"
        )
    except Exception:
        logger.exception("voice reply TTS failed; falling back to <Say>")

    call_id = secrets.token_urlsafe(12)
    voice_session.put(call_id, audio_name, reply)

    try:
        twiml_url = _public_url(f"/twilio/voice/say/{call_id}")
        make_call(caller, twiml_url)
    except Exception:
        logger.exception("outbound call failed")

    # Broadcast voice reply to UI
    ws_hub.fire(caller, channel="voice", direction="out",
                body=reply[:1400], lang=final_lang)

    try:
        send_whatsapp(wa_to, f"📞 Result:\n{reply[:1400]}")
    except Exception:
        logger.exception("twilio WA result send failed")
