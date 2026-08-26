"""The shared generate → validate → retry loop.

Every content type follows the same pipeline:

1. render the **type-specific** prompt template,
2. ask the LLM for drafts constrained to that type's draft schema,
3. resolve the citations the model claimed against real retrieved evidence,
4. build the full item and enrich it with an Instagram payload + score,
5. validate it, drop it if it fails, and retry until the batch is filled.

Subclasses supply only step 4's draft → item mapping. Rejections are counted by
cause (schema, duplicate, ungrounded) so the dashboard can show *why* a batch
came back short instead of silently returning fewer items.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Protocol, Sequence

from pydantic import BaseModel

from app.prompts import get_template
from app.retrieval.context_builder import ContextPack
from app.schemas import DRAFT_SCHEMAS, ITEM_SCHEMAS
from app.schemas.base import BaseItem
from app.schemas.common import FACTUAL_TYPES, ContentType, Difficulty, Sport
from app.services.citation_service import build_grounding
from app.services.engagement_service import enrich
from app.services.llm_service import LLMError, LLMService, get_llm_service
from app.utils.helpers import fingerprint
from app.utils.validators import validate_item

logger = logging.getLogger(__name__)

#: Ask for a couple of spares so one bad draft doesn't force a second API call.
OVERSAMPLE = 2


class NoveltyGuard(Protocol):
    """Cross-session dedup contract, satisfied by ``agent.freshness.NoveltyLedger``.

    ``text`` is passed alongside the fingerprint so an implementation can do
    fuzzy near-duplicate matching, not just exact hash equality.
    """

    def is_duplicate(self, fp: str, *, text: str) -> bool: ...

    def remember(self, fp: str, *, text: str, content_type: str) -> None: ...


@dataclass
class GenerationResult:
    """Accepted items plus a per-cause account of everything discarded."""

    items: list[BaseItem] = field(default_factory=list)
    schema_rejections: int = 0
    duplicate_rejections: int = 0
    ungrounded_rejections: int = 0
    llm_calls: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def rejected(self) -> int:
        return (
            self.schema_rejections
            + self.duplicate_rejections
            + self.ungrounded_rejections
        )

    def merge(self, other: "GenerationResult") -> None:
        self.items.extend(other.items)
        self.schema_rejections += other.schema_rejections
        self.duplicate_rejections += other.duplicate_rejections
        self.ungrounded_rejections += other.ungrounded_rejections
        self.llm_calls += other.llm_calls
        self.warnings.extend(other.warnings)


class BaseGenerator(ABC):
    """One generator per content type; the loop lives here, the mapping there."""

    content_type: ContentType

    def __init__(self, llm: LLMService | None = None) -> None:
        self.llm = llm or get_llm_service()

    # ---------------------------------------------------------------- registries

    @property
    def template(self):
        return get_template(self.content_type)

    @property
    def draft_cls(self) -> type[BaseModel]:
        return DRAFT_SCHEMAS[self.content_type]

    @property
    def item_cls(self) -> type[BaseItem]:
        return ITEM_SCHEMAS[self.content_type]

    @property
    def is_factual(self) -> bool:
        return self.content_type in FACTUAL_TYPES

    # ------------------------------------------------------------------ mapping

    @abstractmethod
    def to_item(
        self,
        draft: BaseModel,
        *,
        sport: Sport,
        difficulty: Difficulty,
        context: ContextPack,
    ) -> BaseItem:
        """Map a validated draft onto the full item envelope.

        Raise ``ValueError`` to reject a draft that is structurally fine but
        fails a type-specific quality bar (e.g. an MCQ that leaks its own
        answer). The loop counts it as a schema rejection and moves on.
        """

    def _grounding_for(self, draft: BaseModel, context: ContextPack):
        """Resolve the draft's claimed citations. Polls have none by design."""
        return build_grounding(
            content_type=self.content_type,
            cited_refs=list(getattr(draft, "cited_refs", []) or []),
            context=context,
            confidence=getattr(draft, "confidence", "medium"),
        )

    # --------------------------------------------------------------------- loop

    def generate(
        self,
        *,
        sport: Sport,
        difficulty: Difficulty,
        count: int,
        context: ContextPack,
        topic: str = "",
        avoid: Sequence[str] = (),
        novelty: NoveltyGuard | None = None,
        require_grounding: bool = True,
        max_attempts: int = 2,
    ) -> GenerationResult:
        """Produce up to ``count`` valid, novel, grounded items of this type."""
        result = GenerationResult()

        # Fingerprints already claimed inside this batch, plus anything the
        # caller explicitly asked us to steer away from.
        local_seen: set[str] = {fingerprint(a) for a in avoid if a.strip()}
        recent: list[str] = [a for a in avoid if a.strip()]

        # Factual generation with no evidence can only hallucinate. Fail fast
        # rather than burning tokens on items the validator will reject.
        if self.is_factual and require_grounding and not context.sources:
            result.warnings.append(
                f"{self.content_type.value}: no evidence retrieved, so no "
                "grounded item could be generated."
            )
            return result

        for attempt in range(1, max_attempts + 1):
            missing = count - len(result.items)
            if missing <= 0:
                break

            drafts, calls = self._request_drafts(
                sport=sport,
                difficulty=difficulty,
                count=missing + (OVERSAMPLE if attempt == 1 else 0),
                topic=topic,
                context=context,
                recent=recent,
                result=result,
            )
            result.llm_calls += calls
            if not drafts:
                break

            for draft in drafts:
                if len(result.items) >= count:
                    break
                item = self._accept(
                    draft,
                    sport=sport,
                    difficulty=difficulty,
                    context=context,
                    local_seen=local_seen,
                    novelty=novelty,
                    require_grounding=require_grounding,
                    result=result,
                )
                if item is not None:
                    recent.append(item.dedup_text())

        if len(result.items) < count:
            result.warnings.append(
                f"{self.content_type.value}: asked for {count}, returned "
                f"{len(result.items)} after {result.rejected} rejection(s)."
            )
        return result

    def _request_drafts(
        self,
        *,
        sport: Sport,
        difficulty: Difficulty,
        count: int,
        topic: str,
        context: ContextPack,
        recent: list[str],
        result: GenerationResult,
    ) -> tuple[list[BaseModel], int]:
        """One LLM call, using this type's own template."""
        template = self.template
        user = template.render_user(
            sport=sport,
            # Difficulty is meaningless for opinion polls; the poll template
            # ignores it and receives None.
            difficulty=difficulty if template.factual else None,
            count=count,
            topic=topic,
            context_text=context.text,
            recent=recent[-12:],
        )
        before = self.llm.call_count
        try:
            drafts = self.llm.generate_batch(
                draft_cls=self.draft_cls,
                system=template.system,
                user=user,
                count=count,
            )
        except LLMError as exc:
            logger.warning("%s generation failed: %s", self.content_type.value, exc)
            result.warnings.append(f"{self.content_type.value}: {exc}")
            return [], max(self.llm.call_count - before, 0)
        return list(drafts), max(self.llm.call_count - before, 0)

    def _accept(
        self,
        draft: BaseModel,
        *,
        sport: Sport,
        difficulty: Difficulty,
        context: ContextPack,
        local_seen: set[str],
        novelty: NoveltyGuard | None,
        require_grounding: bool,
        result: GenerationResult,
    ) -> BaseItem | None:
        """Validate one draft, keeping it only if every gate passes."""
        try:
            item = self.to_item(
                draft, sport=sport, difficulty=difficulty, context=context
            )
        # Pydantic's ValidationError subclasses ValueError, so this catches both
        # schema violations and a generator's own quality guards.
        except ValueError as exc:
            logger.debug("%s draft rejected: %s", self.content_type.value, exc)
            result.schema_rejections += 1
            return None

        enrich(item)

        errors, warnings = validate_item(item, require_grounding=require_grounding)
        if errors:
            # Classify by cause so the dashboard can distinguish "the model got
            # the shape wrong" from "we had no evidence for this claim".
            if self.is_factual and not item.grounding.is_grounded:
                result.ungrounded_rejections += 1
            else:
                result.schema_rejections += 1
            logger.debug("%s item rejected: %s", self.content_type.value, errors)
            return None

        fp = fingerprint(item.dedup_text())
        if fp in local_seen or (
            novelty is not None
            and novelty.is_duplicate(fp, text=item.dedup_text())
        ):
            result.duplicate_rejections += 1
            return None

        item.fingerprint = fp
        local_seen.add(fp)
        if novelty is not None:
            novelty.remember(
                fp,
                text=item.dedup_text(),
                content_type=self.content_type.value,
            )

        result.items.append(item)
        result.warnings.extend(f"{item.id}: {w}" for w in warnings)
        return item
