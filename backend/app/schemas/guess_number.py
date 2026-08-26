"""Guess the Number — a numeric target plus an accepted tolerance range."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

from app.schemas.base import BaseItem
from app.schemas.common import ContentType


class GuessNumberDraft(BaseModel):
    """The exact shape the LLM must return for a guess-the-number item."""

    question: str = Field(
        description="A question whose answer is a single specific number, e.g. "
        "'How many runs did Virat Kohli score in the 2023 ODI World Cup?'"
    )
    target: float = Field(description="The exact correct number.")
    tolerance: float = Field(
        gt=0,
        description="Accepted +/- margin. Scale it to the magnitude of the answer "
        "(e.g. +/-5 for a number near 100, +/-1 for a number under 20).",
    )
    unit: str = Field(
        default="",
        description="Unit of the number if any, e.g. 'runs', 'goals', 'titles'. "
        "Empty string when the number is a bare count.",
    )
    explanation: str = Field(description="One or two sentences giving the exact figure.")
    cited_refs: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"

    @field_validator("question", "explanation")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("field must not be empty")
        return v.strip()

    @model_validator(mode="after")
    def _tolerance_is_sane(self) -> "GuessNumberDraft":
        # A tolerance wide enough to swallow the answer makes the item trivial.
        magnitude = abs(self.target)
        if magnitude > 0 and self.tolerance > magnitude * 0.5:
            raise ValueError(
                "tolerance must be at most 50% of the target, otherwise any "
                "guess is correct"
            )
        return self


class GuessNumberItem(BaseItem):
    content_type: Literal[ContentType.GUESS_NUMBER] = ContentType.GUESS_NUMBER

    question: str
    target: float
    tolerance: float = Field(gt=0)
    unit: str = ""

    @model_validator(mode="after")
    def _range_is_valid(self) -> "GuessNumberItem":
        if self.tolerance <= 0:
            raise ValueError("guess-the-number requires a positive tolerance")
        return self

    @computed_field  # the spec's "accepted tolerance range", e.g. [137, 147]
    @property
    def accepted_range(self) -> tuple[float, float]:
        return (self.target - self.tolerance, self.target + self.tolerance)

    def is_accepted(self, guess: float) -> bool:
        low, high = self.accepted_range
        return low <= guess <= high

    def _fmt(self, value: float) -> str:
        return str(int(value)) if float(value).is_integer() else f"{value:g}"

    @computed_field
    @property
    def correct_answer(self) -> str:
        base = self._fmt(self.target)
        return f"{base} {self.unit}".strip()

    @computed_field  # pre-formatted for the card, e.g. "137–147 (±5)"
    @property
    def range_label(self) -> str:
        low, high = self.accepted_range
        return f"{self._fmt(low)}–{self._fmt(high)} (±{self._fmt(self.tolerance)})"

    def dedup_text(self) -> str:
        return f"{self.question} :: {self._fmt(self.target)}"
