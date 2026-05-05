"""
Phone-OTP auth stub for the demo UI.

Production should use Twilio Verify (https://www.twilio.com/docs/verify).
For the demo we accept any 6-digit code and issue a signed JWT bearing the
phone number. Replace `_send_otp` and `_verify_otp` with real Twilio calls
when promoting to staging.
"""
from __future__ import annotations

import secrets
import time
from typing import Any

import jwt
from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from app.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])

# Demo-only signing secret. Override via env once we add real auth.
_JWT_SECRET = (settings.twilio_auth_token or "demo-secret-change-me")[:32].ljust(32, "x")
_JWT_ALG = "HS256"
_JWT_TTL = 7 * 24 * 60 * 60  # 7 days

# In-memory OTP store: phone -> (code, expires_at)
_otp_store: dict[str, tuple[str, float]] = {}


class StartReq(BaseModel):
    phone: str = Field(..., min_length=8, max_length=20)


class VerifyReq(BaseModel):
    phone: str = Field(..., min_length=8, max_length=20)
    code: str = Field(..., min_length=4, max_length=8)


def _norm_phone(p: str) -> str:
    p = p.strip().replace(" ", "").replace("-", "")
    if not p.startswith("+"):
        p = "+" + p
    return p


def _send_otp(phone: str, code: str) -> None:
    """
    Demo: log the code; in production this calls Twilio Verify or sends an SMS.
    """
    logger.info(f"OTP for {phone}: {code} (DEMO — never log in production)")


@router.post("/start")
async def auth_start(req: StartReq) -> dict[str, Any]:
    phone = _norm_phone(req.phone)
    code = f"{secrets.randbelow(1_000_000):06d}"
    _otp_store[phone] = (code, time.time() + 5 * 60)
    _send_otp(phone, code)
    return {"sent": True, "phone": phone, "demo_hint": "check uvicorn log"}


@router.post("/verify")
async def auth_verify(req: VerifyReq) -> dict[str, Any]:
    phone = _norm_phone(req.phone)
    entry = _otp_store.get(phone)
    if not entry:
        raise HTTPException(400, "no OTP requested for this phone")
    code, exp = entry
    if time.time() > exp:
        _otp_store.pop(phone, None)
        raise HTTPException(400, "OTP expired")
    if req.code.strip() != code:
        raise HTTPException(401, "invalid OTP")

    _otp_store.pop(phone, None)
    payload = {"phone": phone, "iat": int(time.time()), "exp": int(time.time()) + _JWT_TTL}
    token = jwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALG)
    return {"token": token, "phone": phone, "expires_in": _JWT_TTL}


def verify_jwt(token: str) -> str:
    """Decode and return phone, or raise."""
    try:
        payload = jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALG])
    except jwt.PyJWTError as e:
        raise HTTPException(401, f"invalid token: {e}") from e
    return payload["phone"]
