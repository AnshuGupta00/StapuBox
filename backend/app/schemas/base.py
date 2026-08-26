"""Fields every generated item shares, plus the grounding/QA envelope."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.schemas.common import (
    ContentType,
    Difficulty,
    InstagramPayload,
    Source,
    Sport,
)


def new_id() -> str:
    return uuid.uuid4().hex[:12]


class GroundingInfo(BaseModel):
    """Why we believe a factual item is correct.

    ``cited_refs`` are the handles the model claimed to use; ``resolved_sources``
    are the retrieved sources those handles actually matched. A model that
    invents a handle produces an empty ``resolved_sources``, which the
    validation layer treats as ungrounded.
    """

    cited_refs: list[str] = Field(default_factory=list)
    resolved_sources: list[Source] = Field(default_factory=list)
    fact_checked: bool = True
    confidence: Literal["high", "medium", "low"] = "medium"
    reasoning: str = Field(
        default="",
        description="One line on which evidence establishes the answer.",
    )

    @computed_field  # surfaced to the dashboard's grounding badge
    @property
    def is_grounded(self) -> bool:
        return bool(self.resolved_sources)


class BaseItem(BaseModel):
    """Common envelope for all five content types.

    Subclasses add their own answer shape and enforce the type-specific
    invariants from the spec via Pydantic validators.
    """

    model_config = ConfigDict(use_enum_values=False, validate_assignment=True)

    id: str = Field(default_factory=new_id)
    content_type: ContentType
    sport: Sport
    difficulty: Difficulty
    explanation: str = Field(default="", max_length=500)

    grounding: GroundingInfo = Field(default_factory=GroundingInfo)
    instagram: InstagramPayload | None = None
    engagement_score: int = Field(default=0, ge=0, le=100)

    #: Stable hash of the underlying fact, used for cross-session dedup.
    fingerprint: str = ""

    def dedup_text(self) -> str:  # pragma: no cover - overridden by subclasses
        """Text that identifies the underlying fact for novelty checks."""
        raise NotImplementedError
