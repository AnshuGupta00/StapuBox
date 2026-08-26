"""Retrieval routing — decide *how* to ground a batch before generating it.

Not every request needs the same evidence. Web search costs latency and tokens;
the vector DB is free but only holds settled history. This module picks a
strategy from the request, then hands each content type the view of the evidence
that type should see.

The routing rules, and why:

* **Opinion-only batches skip web search.** A This-or-That poll has nothing to
  fact-check, so paying for live search buys nothing. It still reads the
  knowledge base for current names and rivalries.
* **A topic turns web search on.** "IPL 2026" is a request for fresh facts by
  definition.
* **Hard difficulty widens the vector DB sweep.** Obscure records need more
  candidate evidence to find one the model can actually cite.
* **Polls never receive a citable source table.** ``opinion_context`` swaps the
  handles for a single ``OPINION`` marker, so a poll physically cannot present a
  factual citation.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings, get_settings
from app.retrieval.chroma_client import KnowledgeBase
from app.retrieval.context_builder import ContextPack, build_context, opinion_context
from app.schemas.common import FACTUAL_TYPES, ContentType, Difficulty, Sport
from app.schemas.response import RetrievalReport
from app.services.llm_service import LLMService

#: Vector DB results per request, by difficulty.
KB_RESULTS = {
    Difficulty.EASY: 6,
    Difficulty.MEDIUM: 8,
    Difficulty.HARD: 12,
}


@dataclass
class RetrievalPlan:
    """The chosen strategy, with the reasoning kept for the diagnostics panel."""

    use_web_search: bool
    kb_results: int
    reasons: list[str]


def plan_retrieval(
    *,
    content_types: list[ContentType],
    difficulty: Difficulty,
    topic: str = "",
    requested_web_search: bool = True,
    settings: Settings | None = None,
) -> RetrievalPlan:
    settings = settings or get_settings()
    reasons: list[str] = []

    needs_facts = any(ct in FACTUAL_TYPES for ct in content_types)
    use_web = requested_web_search and settings.enable_web_search

    if not settings.enable_web_search:
        reasons.append("Web search disabled by configuration.")
    elif not requested_web_search:
        reasons.append("Web search switched off for this request.")
    elif not needs_facts and not topic.strip():
        use_web = False
        reasons.append(
            "Opinion-only batch — nothing to fact-check, so web search was skipped."
        )
    elif topic.strip():
        reasons.append(
            f"Web search requested: topic '{topic.strip()}' needs current facts."
        )
    else:
        reasons.append("Web search requested for fresh, verifiable facts.")

    kb_results = KB_RESULTS.get(difficulty, 8)
    if difficulty is Difficulty.HARD:
        reasons.append("Hard difficulty: widened the knowledge base sweep.")

    return RetrievalPlan(use_web_search=use_web, kb_results=kb_results, reasons=reasons)


def retrieve(
    *,
    plan: RetrievalPlan,
    sport: Sport,
    difficulty: Difficulty,
    topic: str = "",
    llm: LLMService | None = None,
    knowledge_base: KnowledgeBase | None = None,
) -> ContextPack:
    """Execute the plan once for the whole batch, then reuse the evidence.

    One research pass per request keeps every item in a batch citing the same
    verified evidence, and keeps the API call count proportional to requests
    rather than to items.
    """
    pack = build_context(
        sport=sport,
        difficulty=difficulty,
        topic=topic,
        use_web_search=plan.use_web_search,
        kb_results=plan.kb_results,
        knowledge_base=knowledge_base,
        llm=llm,
    )
    pack.messages = plan.reasons + pack.messages
    return pack


def context_for(content_type: ContentType, pack: ContextPack) -> ContextPack:
    """The view of the evidence a given content type is allowed to cite."""
    if content_type in FACTUAL_TYPES:
        return pack
    return opinion_context(pack)


def to_report(pack: ContextPack) -> RetrievalReport:
    """Flatten a context pack into the API's retrieval report."""
    return RetrievalReport(
        web_search_used=pack.web_used,
        web_results=pack.web_results,
        vector_db_hits=pack.vector_hits,
        sources=list(pack.sources),
        notes=pack.research_notes,
        degraded=pack.degraded,
        messages=list(pack.messages),
    )
