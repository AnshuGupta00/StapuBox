"""MCQ generation template."""

from __future__ import annotations

from dataclasses import dataclass

from app.prompts.base import (
    build_system_prompt,
    render_avoid_block,
    render_context_block,
    render_task_header,
)
from app.schemas.common import ContentType, Difficulty, Sport

TYPE_RULES = """\
FORMAT — MULTIPLE CHOICE QUESTION:
- One clear question with exactly FOUR options and exactly ONE correct answer.
- `correct_index` is the zero-based position of the correct option (0-3).
- Vary where the answer sits across the batch — do not always use index 0.
- All four options must be the same category of thing (four players, or four
  years, or four teams) so the answer is not obvious from the shape alone.
- The question must be answerable without seeing the options."""

SYSTEM_PROMPT = build_system_prompt(TYPE_RULES, factual=True)

# Kept for backwards compatibility with the original scaffold import name.
MCQ_PROMPT = SYSTEM_PROMPT


@dataclass(frozen=True)
class MCQTemplate:
    content_type: ContentType = ContentType.MCQ
    system: str = SYSTEM_PROMPT
    factual: bool = True

    def render_user(
        self,
        *,
        sport: Sport,
        difficulty: Difficulty,
        count: int,
        topic: str,
        context_text: str,
        recent: list[str],
    ) -> str:
        blocks = [
            render_task_header(
                sport=sport, difficulty=difficulty, count=count, topic=topic
            ),
            render_context_block(context_text),
            render_avoid_block(recent),
            f"Write {count} multiple-choice question(s) now.",
        ]
        return "\n\n".join(b for b in blocks if b)


TEMPLATE = MCQTemplate()
