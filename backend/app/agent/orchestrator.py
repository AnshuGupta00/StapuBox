"""The agent loop: retrieve once, generate per type, mix, and report.

``ContentAgent`` is the single entry point the API layer talks to. One request
produces one retrieval pass whose evidence every item in the batch cites, so the
grounding story is consistent and the API call count scales with requests rather
than items.

Mixed batches are built per type and then round-robin interleaved, so a request
for 5 items across 3 types comes back alternating rather than clumped.
"""

from __future__ import annotations

import logging
import uuid

from app.agent.freshness import NoveltyLedger, get_ledger
from app.agent.router import RetrievalPlan, context_for, plan_retrieval, retrieve, to_report
from app.generators import GenerationResult, get_generator
from app.retrieval.chroma_client import KnowledgeBase
from app.retrieval.context_builder import ContextPack
from app.schemas.base import BaseItem
from app.schemas.common import FACTUAL_TYPES, ContentType, Difficulty, Sport
from app.schemas.request import GenerateRequest, RegenerateRequest
from app.schemas.response import (
    BatchDiagnostics,
    BatchInsights,
    GenerateResponse,
    RegenerateResponse,
)
from app.services.engagement_service import batch_insights
from app.services.llm_service import LLMService, get_llm_service
from app.utils.helpers import interleave

logger = logging.getLogger(__name__)


def allocate(count: int, content_types: list[ContentType]) -> dict[ContentType, int]:
    """Spread ``count`` items across the requested types as evenly as possible.

    5 items over 3 types -> ``{first: 2, second: 2, third: 1}``. Earlier types in
    the request get the remainder, so the caller's ordering is meaningful.
    """
    if not content_types:
        return {}
    base, extra = divmod(count, len(content_types))
    return {
        ct: base + (1 if i < extra else 0)
        for i, ct in enumerate(content_types)
        if base + (1 if i < extra else 0) > 0
    }


class ContentAgent:
    """Orchestrates retrieval, per-type generation, dedup and reporting."""

    def __init__(
        self,
        llm: LLMService | None = None,
        ledger: NoveltyLedger | None = None,
        knowledge_base: KnowledgeBase | None = None,
    ) -> None:
        self.llm = llm or get_llm_service()
        self.ledger = ledger or get_ledger()
        self.knowledge_base = knowledge_base

    # ----------------------------------------------------------------- batching

    def generate(self, request: GenerateRequest) -> GenerateResponse:
        plan = plan_retrieval(
            content_types=request.content_types,
            difficulty=request.difficulty,
            topic=request.topic,
            requested_web_search=request.use_web_search,
        )
        pack = self._retrieve(plan, request.sport, request.difficulty, request.topic)

        totals = GenerationResult()
        groups: list[list[BaseItem]] = []

        for content_type, wanted in allocate(
            request.count, request.content_types
        ).items():
            result = self._generate_one_type(
                content_type=content_type,
                sport=request.sport,
                difficulty=request.difficulty,
                topic=request.topic,
                count=wanted,
                pack=pack,
            )
            groups.append(result.items)
            totals.merge(result)

        # Mix the types through the batch instead of returning them clumped.
        items = interleave(groups) if len(groups) > 1 else totals.items

        return GenerateResponse(
            batch_id=uuid.uuid4().hex[:12],
            items=items,
            retrieval=to_report(pack),
            diagnostics=self._diagnostics(request.count, totals),
            insights=BatchInsights.model_validate(batch_insights(items)),
        )

    def regenerate(self, request: RegenerateRequest) -> RegenerateResponse:
        """Replace a single item, forced away from everything already shown."""
        plan = plan_retrieval(
            content_types=[request.content_type],
            difficulty=request.difficulty,
            topic=request.topic,
            requested_web_search=request.use_web_search,
        )
        pack = self._retrieve(plan, request.sport, request.difficulty, request.topic)

        result = self._generate_one_type(
            content_type=request.content_type,
            sport=request.sport,
            difficulty=request.difficulty,
            topic=request.topic,
            count=1,
            pack=pack,
            avoid=request.avoid,
            # A regenerate is a retry by definition: try harder before giving up.
            max_attempts=3,
        )

        return RegenerateResponse(
            item=result.items[0] if result.items else None,
            retrieval=to_report(pack),
            diagnostics=self._diagnostics(1, result),
        )

    # ------------------------------------------------------------------ helpers

    def _retrieve(
        self,
        plan: RetrievalPlan,
        sport: Sport,
        difficulty: Difficulty,
        topic: str,
    ) -> ContextPack:
        return retrieve(
            plan=plan,
            sport=sport,
            difficulty=difficulty,
            topic=topic,
            llm=self.llm,
            knowledge_base=self.knowledge_base,
        )

    def _generate_one_type(
        self,
        *,
        content_type: ContentType,
        sport: Sport,
        difficulty: Difficulty,
        topic: str,
        count: int,
        pack: ContextPack,
        avoid: list[str] | None = None,
        max_attempts: int = 2,
    ) -> GenerationResult:
        generator = get_generator(content_type, llm=self.llm)

        # Steer the model away from recent history *before* it drafts, so the
        # ledger is a backstop rather than the only defence against repeats.
        steer = list(avoid or [])
        steer.extend(
            t
            for t in self.ledger.recent_texts(content_type=content_type.value, limit=10)
            if t not in steer
        )

        return generator.generate(
            sport=sport,
            difficulty=difficulty,
            count=count,
            context=context_for(content_type, pack),
            topic=topic,
            avoid=steer,
            novelty=self.ledger,
            require_grounding=content_type in FACTUAL_TYPES,
            max_attempts=max_attempts,
        )

    def _diagnostics(self, requested: int, totals: GenerationResult) -> BatchDiagnostics:
        return BatchDiagnostics(
            requested=requested,
            returned=len(totals.items),
            schema_rejections=totals.schema_rejections,
            duplicate_rejections=totals.duplicate_rejections,
            ungrounded_rejections=totals.ungrounded_rejections,
            llm_calls=totals.llm_calls,
            mock_mode=not self.llm.is_live,
            warnings=totals.warnings,
        )


_agent: ContentAgent | None = None


def get_agent() -> ContentAgent:
    """FastAPI dependency: one agent, sharing the LLM client and ledger."""
    global _agent
    if _agent is None:
        _agent = ContentAgent()
    return _agent
