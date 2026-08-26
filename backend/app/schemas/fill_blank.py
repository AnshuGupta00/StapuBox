"""Fill in the Blank — a sentence containing a blank plus 4 answer options."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

from app.schemas.base import BaseItem
from app.schemas.common import ContentType

#: The canonical blank marker. Models are told to emit exactly this token.
BLANK_TOKEN = "____"

#: Accepts 3+ underscores, or a bracketed placeholder, so a near-miss from the
#: model can be normalised rather than thrown away.
_BLANK_PATTERN = re.compile(r"_{3,}|\[blank\]|\{blank\}", re.IGNORECASE)


class FillBlankDraft(BaseModel):
    """The exact shape the LLM must return for a fill-in-the-blank item."""

    sentence: str = Field(
        description=f"A factual sentence with the missing term replaced by "
        f"'{BLANK_TOKEN}'. Exactly one blank."
    )
    options: list[str] = Field(
        min_length=4, max_length=4, description="Exactly four distinct candidate fills."
    )
    correct_index: int = Field(
        ge=0, le=3, description="Zero-based index of the option that correctly fills the blank."
    )
    explanation: str = Field(description="One or two sentences explaining the answer.")
    cited_refs: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"

    @field_validator("sentence")
    @classmethod
    def _exactly_one_blank(cls, v: str) -> str:
        cleaned = v.strip()
        matches = _BLANK_PATTERN.findall(cleaned)
        if len(matches) != 1:
            raise ValueError(
                f"sentence must contain exactly one blank marker "
                f"(found {len(matches)}); use '{BLANK_TOKEN}'"
            )
        # Normalise whatever marker the model used to the canonical token.
        return _BLANK_PATTERN.sub(BLANK_TOKEN, cleaned)

    @field_validator("options")
    @classmethod
    def _four_distinct(cls, v: list[str]) -> list[str]:
        cleaned = [o.strip() for o in v]
        if any(not o for o in cleaned):
            raise ValueError("fill-in-the-blank options must be non-empty")
        if len({o.casefold() for o in cleaned}) != 4:
            raise ValueError("fill-in-the-blank options must be four distinct values")
        return cleaned

    @field_validator("explanation")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("explanation must not be empty")
        return v.strip()


class FillBlankItem(BaseItem):
    content_type: Literal[ContentType.FILL_BLANK] = ContentType.FILL_BLANK

    sentence: str
    options: list[str] = Field(min_length=4, max_length=4)
    correct_index: int = Field(ge=0, le=3)

    @model_validator(mode="after")
    def _has_blank(self) -> "FillBlankItem":
        if BLANK_TOKEN not in self.sentence:
            raise ValueError(f"sentence must contain the blank marker '{BLANK_TOKEN}'")
        if len(self.options) != 4:
            raise ValueError("fill-in-the-blank must have exactly 4 options")
        return self

    @computed_field
    @property
    def correct_answer(self) -> str:
        return self.options[self.correct_index]

    def completed_sentence(self) -> str:
        """The sentence with the blank filled in — handy for the explanation card."""
        return self.sentence.replace(BLANK_TOKEN, self.correct_answer, 1)

    def dedup_text(self) -> str:
        return f"{self.sentence} :: {self.correct_answer}"
