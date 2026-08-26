"""Web search retrieval.

Search runs **server-side** as an Anthropic tool, so this module is a thin
adapter over :meth:`LLMService.research` rather than an HTTP client for a
third-party search API. That is a deliberate architectural choice: it removes a
second credential and lets Claude iterate on its own queries (and filter results
before they reach the context window) instead of us guessing keywords.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.schemas.common import Difficulty, Source, Sport
from app.services.llm_service import LLMService, get_llm_service


@dataclass
class WebEvidence:
    notes: str = ""
    sources: list[Source] = field(default_factory=list)
    used: bool = False
    degraded: bool = False
    messages: list[str] = field(default_factory=list)


def search_sport_facts(
    *,
    sport: Sport,
    topic: str = "",
    difficulty: Difficulty | None = None,
    llm: LLMService | None = None,
) -> WebEvidence:
    """Fetch fresh, citable facts for a sport via server-side web search."""
    service = llm or get_llm_service()
    result = service.research(sport=sport, topic=topic, difficulty=difficulty)
    return WebEvidence(
        notes=result.notes,
        sources=result.sources,
        used=result.used_web_search,
        degraded=result.degraded,
        messages=list(result.messages),
    )
