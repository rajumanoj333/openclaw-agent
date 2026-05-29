"""
Per-owner agent configuration store.

Each owner picks a SUBSET of agents from the registry (Morpheus, Ritu,
Kiran, Anika, …) for their business. Each enabled agent gets its own
primed OpenClaw session keyed by (phone, agent_slug).

Phase 3 will move this to Postgres. Same API shape.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from threading import Lock

from app.services.agents.registry import (
    AGENT_REGISTRY,
    DEFAULT_AGENT_SLUGS,
    list_agents,
)


# Legacy capability list. Kept for backward compatibility with existing
# clients that still post capabilities — these now map onto agent slugs.
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

# Capability → agent-slug routing. Used when an old client posts the
# capabilities list and we need to translate to enabled_agents.
_CAPABILITY_TO_AGENT: dict[str, str] = {
    "social_media_posts":     "ritu",
    "marketing_campaigns":    "morpheus",
    "poster_design":          "morpheus",
    "customer_replies":       "ritu",
    "brand_strategy":         "anika",
    "competitor_research":    "anika",
    "content_calendar":       "ritu",
    "analytics_summary":      "anika",
}


@dataclass
class AgentConfig:
    """
    Per-owner config. The 'name' field is legacy (was the single agent's
    display name); we keep it for back-compat but routing now uses
    enabled_agents + intent classifier.
    """
    phone: str
    name: str = "Morpheus"
    capabilities: list[str] = field(default_factory=list)
    enabled_agents: list[str] = field(default_factory=list)
    persona_extra: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        d = asdict(self)
        # Hydrate agent display cards for UI consumption
        d["agents"] = [
            AGENT_REGISTRY[s].display_card()
            for s in self.enabled_agents
            if s in AGENT_REGISTRY
        ]
        return d


_store: dict[str, AgentConfig] = {}
_lock = Lock()


def put(cfg: AgentConfig) -> None:
    """
    Save config. Normalizes enabled_agents:
      - drops unknown slugs
      - derives from capabilities if enabled_agents is empty (back-compat)
      - defaults to DEFAULT_AGENT_SLUGS if both lists are empty
    """
    with _lock:
        cfg.updated_at = time.time()
        cfg.enabled_agents = _normalize_agents(
            cfg.enabled_agents, cfg.capabilities
        )
        _store[cfg.phone] = cfg


def get(phone: str) -> AgentConfig | None:
    with _lock:
        return _store.get(phone)


def delete(phone: str) -> bool:
    with _lock:
        return _store.pop(phone, None) is not None


def all_phones() -> list[str]:
    with _lock:
        return list(_store.keys())


def list_available_agents() -> list[dict]:
    """All agent display cards for the picker UI."""
    return [a.display_card() for a in list_agents()]


def _normalize_agents(slugs: list[str], capabilities: list[str]) -> list[str]:
    """Drop unknown, infer from caps if empty, fall back to defaults."""
    known = {s for s in (slugs or []) if s in AGENT_REGISTRY}
    if known:
        # Preserve original ordering, dedup
        return [s for s in slugs if s in known and slugs.count(s)]
    # Infer from capabilities (legacy clients)
    if capabilities:
        inferred = {
            _CAPABILITY_TO_AGENT[c]
            for c in capabilities
            if c in _CAPABILITY_TO_AGENT
        }
        if inferred:
            return [s for s in AGENT_REGISTRY.keys() if s in inferred]
    return list(DEFAULT_AGENT_SLUGS)
