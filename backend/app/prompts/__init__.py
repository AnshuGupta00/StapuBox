"""Type-specific prompt templates, one per content type.

``TEMPLATES`` is the registry the generators use. Adding a sixth content type
means adding a module here and one entry below — no changes to the agent.
"""

from __future__ import annotations

from typing import Protocol

from app.prompts import (
    fill_blank_prompt,
    guess_number_prompt,
    mcq_prompt,
    poll_prompt,
    true_false_prompt,
)
from app.prompts.base import (
    AGENT_IDENTITY,
    DIFFICULTY_GUIDE,
    GROUNDING_CONTRACT,
    OPINION_CONTRACT,
    build_system_prompt,
)
from app.schemas.common import ContentType, Difficulty, Sport


class PromptTemplate(Protocol):
    """Structural contract every type template satisfies."""

    content_type: ContentType
    system: str
    factual: bool

    def render_user(
        self,
        *,
        sport: Sport,
        difficulty: Difficulty | None,
        count: int,
        topic: str,
        context_text: str,
        recent: list[str],
    ) -> str: ...


TEMPLATES: dict[ContentType, PromptTemplate] = {
    ContentType.MCQ: mcq_prompt.TEMPLATE,
    ContentType.TRUE_FALSE: true_false_prompt.TEMPLATE,
    ContentType.POLL: poll_prompt.TEMPLATE,
    ContentType.FILL_BLANK: fill_blank_prompt.TEMPLATE,
    ContentType.GUESS_NUMBER: guess_number_prompt.TEMPLATE,
}


def get_template(content_type: ContentType) -> PromptTemplate:
    try:
        return TEMPLATES[content_type]
    except KeyError:  # pragma: no cover - guarded by the ContentType enum
        raise ValueError(f"No prompt template registered for {content_type}") from None


__all__ = [
    "AGENT_IDENTITY",
    "DIFFICULTY_GUIDE",
    "GROUNDING_CONTRACT",
    "OPINION_CONTRACT",
    "TEMPLATES",
    "PromptTemplate",
    "build_system_prompt",
    "get_template",
]
