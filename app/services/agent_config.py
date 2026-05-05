"""
Per-user agent persona store.

After business onboarding confirms, the user defines their agent: a name,
the list of capabilities the agent is allowed to handle, and an optional
extra system instruction. This is enforced by prepending a system block
to every user message sent to OpenClaw.

Phase 3 will move this to Postgres. Same API shape.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from threading import Lock


# Curated capability list. Showing in UI as checkboxes; agent only handles
# tasks within these scopes.
DEFAULT_CAPABILITIES = [
    "social_media_posts",
    "marketing_campaigns",
    "poster_design",
    "customer_replies",
    "brand_strategy",
    "competitor_research",
    "content_calendar",
    "analytics_summary",
]


@dataclass
class AgentConfig:
    phone: str
    name: str = "Morpheus"
    capabilities: list[str] = field(default_factory=list)
    persona_extra: str = ""        # optional free-form instructions
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


_store: dict[str, AgentConfig] = {}
_lock = Lock()


def put(cfg: AgentConfig) -> None:
    with _lock:
        cfg.updated_at = time.time()
        _store[cfg.phone] = cfg


def get(phone: str) -> AgentConfig | None:
    with _lock:
        return _store.get(phone)


def build_persona_prefix(phone: str, business_name: str | None = None) -> str:
    """
    Build the system-prompt prefix injected before every user message.
    Returns "" when no config exists yet.
    """
    cfg = get(phone)
    if not cfg:
        return ""

    caps_human = ", ".join(c.replace("_", " ") for c in cfg.capabilities) or "general assistance"
    biz = business_name or "the user's business"

    parts = [
        f"You are {cfg.name}, a marketing-focused AI employee for {biz}.",
        f"Your scope is strictly: {caps_human}.",
        "If the user asks for something outside your scope, politely decline and "
        "suggest the closest in-scope alternative.",
        "Always respect the brand colors, tone, and visual style on file.",
    ]
    if cfg.persona_extra.strip():
        parts.append(cfg.persona_extra.strip())

    return "\n".join(parts)
