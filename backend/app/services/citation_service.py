"""Resolve model-claimed citations against real retrieved evidence.

The model is asked to cite handles (``W2``, ``K5``) that appear in the context
pack. This module converts those claims into a :class:`GroundingInfo`, keeping
only handles that resolve to evidence we actually retrieved. An invented handle
resolves to nothing, which the validation layer then treats as ungrounded — so a
hallucinated citation degrades into a rejection rather than a false claim of
provenance.
"""

from __future__ import annotations

from typing import Protocol

from app.schemas.base import GroundingInfo
from app.schemas.common import FACTUAL_TYPES, ContentType, Source, SourceKind


class RefResolver(Protocol):
    """Anything that can turn citation handles into real sources.

    Declared structurally rather than importing ``ContextPack`` so the service
    layer stays independent of the retrieval layer (and free of an import cycle).
    """

    def resolve(self, refs: list[str]) -> list[Source]: ...


def build_grounding(
    *,
    content_type: ContentType,
    cited_refs: list[str],
    context: RefResolver,
    confidence: str = "medium",
) -> GroundingInfo:
    """Turn claimed refs into verified grounding metadata."""
    if content_type not in FACTUAL_TYPES:
        return GroundingInfo(
            cited_refs=[],
            resolved_sources=[],
            fact_checked=False,
            confidence="medium",
            reasoning="Opinion-based format — intentionally not fact-checked.",
        )

    resolved = context.resolve(cited_refs)
    return GroundingInfo(
        cited_refs=[r.strip().upper() for r in cited_refs],
        resolved_sources=resolved,
        fact_checked=bool(resolved),
        confidence=_adjust_confidence(confidence, bool(resolved)),
        reasoning=_describe(resolved),
    )


def _adjust_confidence(reported: str, grounded: bool) -> str:
    """Never let an ungrounded item claim high confidence."""
    reported = reported if reported in {"high", "medium", "low"} else "medium"
    if not grounded:
        return "low"
    return reported


def _describe(resolved: list) -> str:
    if not resolved:
        return "No retrieved source could be matched to this claim."
    web = sum(1 for s in resolved if s.kind is SourceKind.WEB_SEARCH)
    kb = sum(1 for s in resolved if s.kind is SourceKind.VECTOR_DB)
    parts = []
    if web:
        parts.append(f"{web} web search result{'s' if web != 1 else ''}")
    if kb:
        parts.append(f"{kb} knowledge base entr{'ies' if kb != 1 else 'y'}")
    return "Supported by " + " and ".join(parts) + "."


def citation_labels(grounding: GroundingInfo) -> list[str]:
    """Human-readable provenance lines for the UI."""
    return [f"{s.ref} · {s.label()}" for s in grounding.resolved_sources]
