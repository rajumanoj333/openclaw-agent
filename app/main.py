from fastapi import FastAPI
from loguru import logger

from app.config import settings
from app.routes import audio, voice, whatsapp

app = FastAPI(title="OpenClaw Twilio Agent", version="0.1.0")

app.include_router(whatsapp.router)
app.include_router(voice.router)
app.include_router(audio.router)


@app.get("/")
async def root():
    return {"service": "openclaw-agent", "env": settings.app_env}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.on_event("startup")
async def startup_event():
    logger.info(f"App starting in {settings.app_env} mode on port {settings.app_port}")
