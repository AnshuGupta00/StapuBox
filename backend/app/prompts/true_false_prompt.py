"""True/False generation template."""

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
FORMAT — TRUE / FALSE:
- Write a DECLARATIVE statement, never a question. No question marks.
- The statement must be unambiguously true or unambiguously false. Avoid
  "arguably", "widely considered", "one of the best" — those are opinions.
- Balance the batch: roughly half true, half false. Do not make every answer
  true, and do not alternate in an obvious pattern.
- Build false statements by taking a real fact and changing ONE precise detail
  (the year, the opponent, the number, the venue). A false statement should feel
  believable, not absurd.
- Anchor statements in specifics. "Brazil has won five FIFA World Cups" is good;
  "Brazil is a strong footballing nation" is not checkable."""

SYSTEM_PROMPT = build_system_prompt(TYPE_RULES, factual=True)

TRUE_FALSE_PROMPT = SYSTEM_PROMPT


@dataclass(frozen=True)
class TrueFalseTemplate:
    content_type: ContentType = ContentType.TRUE_FALSE
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
            f"Write {count} true/false statement(s) now. Mix true and false verdicts.",
        ]
        return "\n\n".join(b for b in blocks if b)


TEMPLATE = TrueFalseTemplate()
