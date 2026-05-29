"""Central agent registry + lookup + intent routing."""
from __future__ import annotations

import re

from app.services.agents.anika import anika
from app.services.agents.base import Agent
from app.services.agents.kiran import kiran
from app.services.agents.morpheus import morpheus
from app.services.agents.ritu import ritu


# Slug → Agent. Order matters: first-listed is the default fallback.
AGENT_REGISTRY: dict[str, Agent] = {
    "morpheus": morpheus,
    "ritu":     ritu,
    "kiran":    kiran,
    "anika":    anika,
}

# Default selection for a brand-new onboarding (owner can toggle in UI).
DEFAULT_AGENT_SLUGS: list[str] = ["morpheus", "ritu"]


def get_agent(slug: str) -> Agent | None:
    """Lookup by slug. Returns None if unknown."""
    return AGENT_REGISTRY.get(slug)


def list_agents() -> list[Agent]:
    """All agents in registry order."""
    return list(AGENT_REGISTRY.values())


def route_message(
    text: str, enabled_slugs: list[str]
) -> str:
    """
    Pick the best agent slug for an incoming user message.

    Strategy:
      1. Check each enabled agent's intent_keywords against the text.
      2. Pick the agent with the most keyword hits.
      3. Tie-break: registry order (Morpheus wins over Ritu wins over Kiran).
      4. If zero hits: return first enabled slug as fallback.
      5. If enabled_slugs is empty: return Morpheus (registry default).

    Returns the chosen agent's slug. Caller uses this to pick the primed
    OpenClaw session.
    """
    if not enabled_slugs:
        return "morpheus"
    t = (text or "").lower()
    best_slug = enabled_slugs[0]
    best_hits = 0
    for slug in enabled_slugs:
        agent = AGENT_REGISTRY.get(slug)
        if not agent:
            continue
        hits = sum(
            1 for kw in agent.intent_keywords
            if re.search(rf"\b{re.escape(kw)}\b", t)
        )
        if hits > best_hits:
            best_hits = hits
            best_slug = slug
    return best_slug
