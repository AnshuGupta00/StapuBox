"""Inbound API request models."""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import ContentType, Difficulty, Sport


class GenerateRequest(BaseModel):
    """A batch generation request.

    Leave ``content_types`` empty (or pass more than one) to get a mixed batch.
    """

    sport: Sport
    difficulty: Difficulty = Difficulty.MEDIUM
    content_types: list[ContentType] = Field(
        default_factory=list,
        description="Types to draw from. Empty means 'mix all five'.",
    )
    count: int = Field(default=5, ge=1, le=10, description="Items to generate (spec default 4-5).")
    topic: str = Field(
        default="",
        max_length=200,
        description="Optional focus, e.g. 'IPL 2026' or 'Grand Slam finals'.",
    )
    use_web_search: bool = Field(
        default=True, description="Ground on live web results as well as the vector DB."
    )

    @model_validator(mode="after")
    def _default_to_mixed(self) -> "GenerateRequest":
        if not self.content_types:
            self.content_types = list(ContentType)
        # Preserve caller order but drop duplicates.
        seen: set[ContentType] = set()
        deduped: list[ContentType] = []
        for ct in self.content_types:
            if ct not in seen:
                seen.add(ct)
                deduped.append(ct)
        self.content_types = deduped
        return self

    @property
    def is_mixed(self) -> bool:
        return len(self.content_types) > 1


class RegenerateRequest(BaseModel):
    """Regenerate one item, keeping its type and slot in the batch."""

    sport: Sport
    difficulty: Difficulty = Difficulty.MEDIUM
    content_type: ContentType
    topic: str = Field(default="", max_length=200)
    use_web_search: bool = True
    avoid: list[str] = Field(
        default_factory=list,
        description="Fingerprints or question text already shown, to force a different fact.",
    )
