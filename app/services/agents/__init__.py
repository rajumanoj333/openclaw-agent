"""
Agent registry. One business owner can enable many named agents, each
with a tight scope. OpenClaw orchestrates routing.

Architecture (mirrors the Eraser diagram):
  - Owner signs in (phone = routing key)
  - Onboarding scrapes business → confirm → pick agents (multi-select)
  - OpenClaw VM = orchestrator (one process, many primed sessions)
  - Each agent: separate primed OpenClaw session keyed by (phone, agent_slug)
  - Intent classifier decides which agent answers each inbound message
"""
from app.services.agents.registry import (
    AGENT_REGISTRY,
    get_agent,
    list_agents,
    DEFAULT_AGENT_SLUGS,
)
from app.services.agents.base import Agent

__all__ = [
    "Agent",
    "AGENT_REGISTRY",
    "get_agent",
    "list_agents",
    "DEFAULT_AGENT_SLUGS",
]
