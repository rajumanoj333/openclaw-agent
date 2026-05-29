"""Agent definition — shape of a single named agent in the registry."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Agent:
    """
    Static definition of a named agent. Multiple businesses share the same
    Agent definitions; per-business state lives in BusinessProfile +
    enabled_agents list + per-(phone, slug) primed flag.

    Fields:
      slug          — stable identifier ("ritu", "kiran", "anika", "morpheus")
      name          — display name shown in UI
      role          — one-line role title
      icon          — lucide-react icon name (UI hint)
      color         — Tailwind color token (UI accent)
      scope         — short bullet list of what this agent handles
      persona       — voice + behavior cues (becomes part of system prompt)
      core_prompt   — task-specific instructions, output shape, triggers
      intent_keywords — words/phrases that route messages to this agent
    """
    slug: str
    name: str
    role: str
    icon: str
    color: str
    scope: list[str]
    persona: str
    core_prompt: str
    intent_keywords: tuple[str, ...] = ()

    def display_card(self) -> dict:
        """Compact dict for UI agent-picker cards."""
        return {
            "slug": self.slug,
            "name": self.name,
            "role": self.role,
            "icon": self.icon,
            "color": self.color,
            "scope": self.scope,
        }
