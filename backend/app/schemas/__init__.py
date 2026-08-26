"""Pydantic schemas: one module per content type, plus shared envelopes.

The ``DRAFT_SCHEMAS`` / ``ITEM_SCHEMAS`` maps are the single source of truth
that ties a :class:`ContentType` to the models used to generate and validate it.
"""

from __future__ import annotations

from app.schemas.base import BaseItem, GroundingInfo, new_id
from app.schemas.common import (
    FACTUAL_TYPES,
    OPINION_TYPES,
    ContentType,
    Difficulty,
    InstagramPayload,
    InstagramSurface,
    Source,
    SourceKind,
    Sport,
)
from app.schemas.fill_blank import BLANK_TOKEN, FillBlankDraft, FillBlankItem
from app.schemas.guess_number import GuessNumberDraft, GuessNumberItem
from app.schemas.mcq import OPTION_LETTERS, MCQDraft, MCQItem
from app.schemas.poll import PollDraft, PollItem
from app.schemas.request import GenerateRequest, RegenerateRequest
from app.schemas.response import (
    BatchDiagnostics,
    ContentItem,
    GenerateResponse,
    RegenerateResponse,
    RetrievalReport,
)
from app.schemas.true_false import TrueFalseDraft, TrueFalseItem

#: What the LLM must return, per type.
DRAFT_SCHEMAS: dict[ContentType, type] = {
    ContentType.MCQ: MCQDraft,
    ContentType.TRUE_FALSE: TrueFalseDraft,
    ContentType.POLL: PollDraft,
    ContentType.FILL_BLANK: FillBlankDraft,
    ContentType.GUESS_NUMBER: GuessNumberDraft,
}

#: What we return to clients, per type.
ITEM_SCHEMAS: dict[ContentType, type[BaseItem]] = {
    ContentType.MCQ: MCQItem,
    ContentType.TRUE_FALSE: TrueFalseItem,
    ContentType.POLL: PollItem,
    ContentType.FILL_BLANK: FillBlankItem,
    ContentType.GUESS_NUMBER: GuessNumberItem,
}

__all__ = [
    "BLANK_TOKEN",
    "OPTION_LETTERS",
    "FACTUAL_TYPES",
    "OPINION_TYPES",
    "DRAFT_SCHEMAS",
    "ITEM_SCHEMAS",
    "BaseItem",
    "BatchDiagnostics",
    "ContentItem",
    "ContentType",
    "Difficulty",
    "FillBlankDraft",
    "FillBlankItem",
    "GenerateRequest",
    "GenerateResponse",
    "GroundingInfo",
    "GuessNumberDraft",
    "GuessNumberItem",
    "InstagramPayload",
    "InstagramSurface",
    "MCQDraft",
    "MCQItem",
    "PollDraft",
    "PollItem",
    "RegenerateRequest",
    "RegenerateResponse",
    "RetrievalReport",
    "Source",
    "SourceKind",
    "Sport",
    "TrueFalseDraft",
    "TrueFalseItem",
    "new_id",
]
