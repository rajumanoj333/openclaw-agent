from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.config import settings
from app.routes import audio, auth, voice, whatsapp, ws
from app.services import voice_prompts

app = FastAPI(title="OpenClaw Twilio Agent", version="0.1.0")

# Frontend (Next.js on Vercel) calls this API + opens a WebSocket.
# In dev allow everything; tighten to the real Vercel domain in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(whatsapp.router)
app.include_router(voice.router)
app.include_router(audio.router)
app.include_router(auth.router)
app.include_router(ws.router)


@app.get("/")
async def root():
    return {"service": "openclaw-agent", "env": settings.app_env}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.on_event("startup")
async def startup_event():
    logger.info(f"App starting in {settings.app_env} mode on port {settings.app_port}")
    try:
        await voice_prompts.ensure_all()
    except Exception:
        logger.exception("voice prompts ensure_all failed; voice calls may use fallback")
