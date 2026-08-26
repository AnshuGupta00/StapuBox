"""Outbound API response models."""

from __future__ import annotations

from typing import Annotated, Union

from pydantic import BaseModel, Field

from app.schemas.common import Source
from app.schemas.fill_blank import FillBlankItem
from app.schemas.guess_number import GuessNumberItem
from app.schemas.mcq import MCQItem
from app.schemas.poll import PollItem
from app.schemas.true_false import TrueFalseItem

#: Discriminated union so FastAPI emits a precise OpenAPI schema and clients
#: can switch on `content_type` without guessing.
ContentItem = Annotated[
    Union[MCQItem, TrueFalseItem, PollItem, FillBlankItem, GuessNumberItem],
    Field(discriminator="content_type"),
]


class RetrievalReport(BaseModel):
    """What retrieval actually contributed, surfaced to the dashboard."""

    web_search_used: bool = False
    web_results: int = 0
    vector_db_hits: int = 0
    sources: list[Source] = Field(default_factory=list)
    notes: str = Field(default="", description="Condensed research digest used for grounding.")
    degraded: bool = Field(
        default=False, description="True when a retrieval backend was unavailable."
    )
    messages: list[str] = Field(default_factory=list)


class BatchDiagnostics(BaseModel):
    """Per-request QA numbers. Makes the grounding claims auditable."""

    requested: int = 0
    returned: int = 0
    schema_rejections: int = 0
    duplicate_rejections: int = 0
    ungrounded_rejections: int = 0
    llm_calls: int = 0
    mock_mode: bool = False
    warnings: list[str] = Field(default_factory=list)


class BatchInsights(BaseModel):
    """Aggregates powering the dashboard's insights panel.

    Computed server-side so the panel and the ranking logic cannot disagree
    about which item in a batch is the strongest.
    """

    count: int = 0
    average_score: int = 0
    best_item_id: str | None = None
    type_mix: dict[str, int] = Field(default_factory=dict)
    surface_mix: dict[str, int] = Field(default_factory=dict)
    grounded: int = Field(default=0, description="Items with at least one resolved source.")
    opinion: int = Field(default=0, description="Items flagged opinion-based, not fact-checked.")
    truncation_warnings: int = 0


class GenerateResponse(BaseModel):
    batch_id: str
    items: list[ContentItem] = Field(default_factory=list)
    retrieval: RetrievalReport = Field(default_factory=RetrievalReport)
    diagnostics: BatchDiagnostics = Field(default_factory=BatchDiagnostics)
    insights: BatchInsights = Field(default_factory=BatchInsights)


class RegenerateResponse(BaseModel):
    item: ContentItem | None = None
    retrieval: RetrievalReport = Field(default_factory=RetrievalReport)
    diagnostics: BatchDiagnostics = Field(default_factory=BatchDiagnostics)
