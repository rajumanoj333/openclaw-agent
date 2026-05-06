"""
In-memory business profile store. Phase E will swap this for Postgres.

A profile groups everything we extracted from the user's onboarding URL:
the LLM-cleaned business info plus the harvested logo + brand colors.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from threading import Lock


@dataclass
class BrandKit:
    primary_color: str | None = None
    secondary_color: str | None = None
    accent_color: str | None = None
    tone: str | None = None              # playful / professional / warm / ...
    visual_style: str | None = None      # modern / minimal / vibrant / ...
    logo_description: str | None = None
    tagline: str | None = None


@dataclass
class BusinessProfile:
    phone: str
    name: str | None = None
    type: str | None = None              # restaurant / clinic / salon / ...
    category: str | None = None
    description: str | None = None
    address: str | None = None
    city: str | None = None
    contact_phone: str | None = None
    email: str | None = None
    website: str | None = None
    socials: dict[str, str] = field(default_factory=dict)
    timings: str | None = None
    services: list[str] = field(default_factory=list)
    pricing_note: str | None = None
    logo_url: str | None = None
    brand: BrandKit = field(default_factory=BrandKit)
    confidence: str = "low"              # high / medium / low
    source_urls: list[str] = field(default_factory=list)
    raw_colors: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    confirmed: bool = False

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


_store: dict[str, BusinessProfile] = {}
_lock = Lock()


def put(profile: BusinessProfile) -> None:
    with _lock:
        _store[profile.phone] = profile


def get(phone: str) -> BusinessProfile | None:
    with _lock:
        return _store.get(phone)


def confirm(phone: str) -> bool:
    with _lock:
        prof = _store.get(phone)
        if not prof:
            return False
        prof.confirmed = True
        return True


def all_phones() -> list[str]:
    with _lock:
        return list(_store.keys())


def delete(phone: str) -> bool:
    """Remove the profile for a phone. Returns True if something was removed."""
    with _lock:
        return _store.pop(phone, None) is not None
