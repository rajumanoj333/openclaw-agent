"""
Phone-OTP auth stub for the demo UI.

Production should use Twilio Verify (https://www.twilio.com/docs/verify).
For the demo we accept any 6-digit code and issue a signed JWT bearing the
phone number. Replace `_send_otp` and `_verify_otp` with real Twilio calls
when promoting to staging.
"""
from __future__ import annotations

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


class LoginReq(BaseModel):
    phone: str = Field(..., min_length=8, max_length=20)


def _norm_phone(p: str) -> str:
    p = p.strip().replace(" ", "").replace("-", "")
    if not p.startswith("+"):
        p = "+" + p
    return p


def _issue_token(phone: str) -> dict[str, Any]:
    payload = {
        "phone": phone,
        "iat": int(time.time()),
        "exp": int(time.time()) + _JWT_TTL,
    }
    token = jwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALG)
    return {"token": token, "phone": phone, "expires_in": _JWT_TTL}


@router.post("/login")
async def auth_login(req: LoginReq) -> dict[str, Any]:
    """
    Demo-grade: accept any phone, return a JWT immediately. No OTP step.
    Replace with Twilio Verify before exposing publicly.
    """
    phone = _norm_phone(req.phone)
    logger.info(f"login phone={phone} (demo mode — no OTP)")
    return _issue_token(phone)


# Back-compat: keep old endpoints as no-ops in case the UI hits them.
@router.post("/start")
async def auth_start_stub(req: LoginReq) -> dict[str, Any]:
    return {"sent": True, "phone": _norm_phone(req.phone), "demo_hint": "demo: any code"}


class VerifyReq(BaseModel):
    phone: str = Field(..., min_length=8, max_length=20)
    code: str = Field(default="000000", min_length=1, max_length=8)


@router.post("/verify")
async def auth_verify_stub(req: VerifyReq) -> dict[str, Any]:
    return _issue_token(_norm_phone(req.phone))


def verify_jwt(token: str) -> str:
    """Decode and return phone, or raise."""
    try:
        payload = jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALG])
    except jwt.PyJWTError as e:
        raise HTTPException(401, f"invalid token: {e}") from e
    return payload["phone"]
