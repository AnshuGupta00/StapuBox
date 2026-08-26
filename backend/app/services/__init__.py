"""Services: LLM access, citation resolution, and engagement packaging."""

from __future__ import annotations

from app.services.citation_service import build_grounding, citation_labels
from app.services.engagement_service import (
    SURFACE_MAP,
    batch_insights,
    build_instagram_payload,
    enrich,
    score_breakdown,
    score_engagement,
)
from app.services.llm_service import (
    LLMError,
    LLMService,
    ResearchResult,
    get_llm_service,
)

__all__ = [
    "LLMError",
    "LLMService",
    "ResearchResult",
    "SURFACE_MAP",
    "batch_insights",
    "build_grounding",
    "build_instagram_payload",
    "citation_labels",
    "enrich",
    "get_llm_service",
    "score_breakdown",
    "score_engagement",
]
