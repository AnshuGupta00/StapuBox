"""This-or-That Poll — exactly 2 options and, by design, no correct answer.

This is the only opinion-based type. The schema actively refuses to carry a
correct answer so a poll can never be presented as fact-checked content.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.base import BaseItem
from app.schemas.common import ContentType


class PollDraft(BaseModel):
    """The exact shape the LLM must return for a This-or-That poll."""

    prompt: str = Field(
        description="A debate-provoking either/or question, e.g. "
        "\"Messi or Ronaldo — who's the greater dribbler?\""
    )
    options: list[str] = Field(
        min_length=2, max_length=2, description="Exactly two opposing choices."
    )
    rationale: str = Field(
        default="",
        description="Why this split divides fans. Framing only — never a verdict.",
    )

    @field_validator("options")
    @classmethod
    def _two_distinct(cls, v: list[str]) -> list[str]:
        cleaned = [o.strip() for o in v]
        if any(not o for o in cleaned):
            raise ValueError("poll options must be non-empty")
        if cleaned[0].casefold() == cleaned[1].casefold():
            raise ValueError("poll options must be two different choices")
        return cleaned

    @field_validator("prompt")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("poll prompt must not be empty")
        return v.strip()


class PollItem(BaseItem):
    content_type: Literal[ContentType.POLL] = ContentType.POLL

    prompt: str
    options: list[str] = Field(min_length=2, max_length=2)

    #: Structural guarantee: opinion content is never fact-checked.
    opinion_based: Literal[True] = True
    correct_answer: Literal[None] = None

    #: Difficulty is meaningless for an opinion poll but kept for a uniform
    #: envelope; the API reports it as "N/A" for polls.
    @model_validator(mode="after")
    def _no_correct_answer(self) -> "PollItem":
        if len(self.options) != 2:
            raise ValueError("Poll must have exactly 2 options")
        if self.correct_answer is not None:
            raise ValueError("Poll must not declare a correct answer")
        if self.grounding.fact_checked:
            # Polls are opinion-based; mark them so the UI can badge them.
            self.grounding.fact_checked = False
        return self

    def dedup_text(self) -> str:
        left, right = sorted(o.casefold() for o in self.options)
        return f"{left} vs {right}"
