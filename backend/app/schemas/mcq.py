"""Multiple Choice Question — exactly 4 options, exactly 1 correct answer."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

from app.schemas.base import BaseItem
from app.schemas.common import ContentType

OPTION_LETTERS = ("A", "B", "C", "D")


class MCQDraft(BaseModel):
    """The exact shape the LLM must return for an MCQ."""

    question: str = Field(description="A single, self-contained factual question.")
    options: list[str] = Field(
        min_length=4, max_length=4, description="Exactly four distinct answer options."
    )
    correct_index: int = Field(
        ge=0, le=3, description="Zero-based index into options of the one correct answer."
    )
    explanation: str = Field(description="One or two sentences explaining the answer.")
    cited_refs: list[str] = Field(
        default_factory=list,
        description="Handles of the context items that prove the answer, e.g. ['W1','K3'].",
    )
    confidence: Literal["high", "medium", "low"] = "medium"

    @field_validator("options")
    @classmethod
    def _options_distinct_and_nonempty(cls, v: list[str]) -> list[str]:
        cleaned = [opt.strip() for opt in v]
        if any(not opt for opt in cleaned):
            raise ValueError("MCQ options must all be non-empty")
        if len({opt.casefold() for opt in cleaned}) != 4:
            raise ValueError("MCQ options must be four distinct values")
        return cleaned

    @field_validator("question", "explanation")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("field must not be empty")
        return v.strip()


class MCQItem(BaseItem):
    content_type: Literal[ContentType.MCQ] = ContentType.MCQ

    question: str
    options: list[str] = Field(min_length=4, max_length=4)
    correct_index: int = Field(ge=0, le=3)

    @model_validator(mode="after")
    def _exactly_one_correct(self) -> "MCQItem":
        # The index-based contract makes "exactly one correct answer"
        # structurally impossible to violate; this guards against an option
        # list mutated after construction.
        if len(self.options) != 4:
            raise ValueError("MCQ must have exactly 4 options")
        if not 0 <= self.correct_index < 4:
            raise ValueError("MCQ correct_index must point at one of the 4 options")
        return self

    @computed_field  # serialised, so the UI never has to index into options
    @property
    def correct_letter(self) -> str:
        return OPTION_LETTERS[self.correct_index]

    @computed_field
    @property
    def correct_answer(self) -> str:
        return self.options[self.correct_index]

    def lettered_options(self) -> list[str]:
        return [f"{OPTION_LETTERS[i]}. {opt}" for i, opt in enumerate(self.options)]

    def dedup_text(self) -> str:
        return f"{self.question} :: {self.correct_answer}"
