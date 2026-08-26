"""True / False — a verifiable statement plus its boolean verdict."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, computed_field, field_validator

from app.schemas.base import BaseItem
from app.schemas.common import ContentType


class TrueFalseDraft(BaseModel):
    """The exact shape the LLM must return for a True/False item."""

    statement: str = Field(
        description="A declarative sentence that is unambiguously true or false. "
        "Never phrase it as a question."
    )
    answer: bool = Field(description="True if the statement is factually correct.")
    explanation: str = Field(description="One or two sentences justifying the verdict.")
    cited_refs: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"

    @field_validator("statement")
    @classmethod
    def _must_be_declarative(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("statement must not be empty")
        if cleaned.endswith("?"):
            raise ValueError("True/False statement must be declarative, not a question")
        return cleaned

    @field_validator("explanation")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("explanation must not be empty")
        return v.strip()


class TrueFalseItem(BaseItem):
    content_type: Literal[ContentType.TRUE_FALSE] = ContentType.TRUE_FALSE

    statement: str
    answer: bool

    @computed_field  # serialised so the API answer field is uniform across types
    @property
    def correct_answer(self) -> str:
        return "True" if self.answer else "False"

    def dedup_text(self) -> str:
        return f"{self.statement} :: {self.correct_answer}"
