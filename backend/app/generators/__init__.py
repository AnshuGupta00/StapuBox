"""Generator registry — one generator per content type.

The registry is the only place that knows the full set of types. Adding a sixth
format means adding a schema pair, a prompt template and a generator, then one
line here; the agent and API layers need no changes.
"""

from __future__ import annotations

from app.generators.base import BaseGenerator, GenerationResult, NoveltyGuard
from app.generators.fill_blank_generator import FillBlankGenerator
from app.generators.guess_number_generator import GuessNumberGenerator
from app.generators.mcq_generator import MCQGenerator
from app.generators.poll_generator import PollGenerator
from app.generators.true_false_generator import TrueFalseGenerator
from app.schemas.common import ContentType
from app.services.llm_service import LLMService

GENERATORS: dict[ContentType, type[BaseGenerator]] = {
    ContentType.MCQ: MCQGenerator,
    ContentType.TRUE_FALSE: TrueFalseGenerator,
    ContentType.POLL: PollGenerator,
    ContentType.FILL_BLANK: FillBlankGenerator,
    ContentType.GUESS_NUMBER: GuessNumberGenerator,
}


def get_generator(
    content_type: ContentType, llm: LLMService | None = None
) -> BaseGenerator:
    try:
        cls = GENERATORS[content_type]
    except KeyError:  # pragma: no cover - guarded by the ContentType enum
        raise ValueError(f"No generator registered for {content_type}") from None
    return cls(llm=llm)


__all__ = [
    "GENERATORS",
    "BaseGenerator",
    "FillBlankGenerator",
    "GenerationResult",
    "GuessNumberGenerator",
    "MCQGenerator",
    "NoveltyGuard",
    "PollGenerator",
    "TrueFalseGenerator",
    "get_generator",
]
