from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.config import settings
from app.routes import audio, auth, instagram, onboarding, system, voice, whatsapp, ws
from app.services import voice_prompts


# ─── Rate limiter ────────────────────────────────────────────────────────
#
# Limits keyed by client IP (X-Forwarded-For when behind Caddy/ngrok).
# Defaults are conservative for hackathon demo. Production: tighten + use
# Redis-backed storage so limits survive process restarts.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["120/minute"],
    headers_enabled=True,  # X-RateLimit-* headers in responses
)


app = FastAPI(title="OpenClaw Twilio Agent", version="0.2.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


# CORS — open in dev, tighten in prod
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.app_env == "dev" else [
        # production allow-list — fill in the real Vercel / Caddy domain
        "https://agent-demo.74-225-254-197.sslip.io",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(whatsapp.router)
app.include_router(voice.router)
app.include_router(audio.router)
app.include_router(auth.router)
app.include_router(onboarding.router)
app.include_router(instagram.router)
app.include_router(system.router)
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
