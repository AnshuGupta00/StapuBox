"""Guess-the-number generation template."""

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
FORMAT — GUESS THE NUMBER:
- The answer must be ONE specific number that the context states outright.
  If the context does not contain the exact figure, choose a different question.
- `target` is that exact number. `unit` names what it counts ("runs", "goals",
  "titles"); use an empty string for a bare count.
- `tolerance` is the accepted +/- margin, and it must be scaled to the answer:
  - answers under 20  -> tolerance 1 to 2
  - answers 20-200    -> tolerance 3 to 10
  - answers 200-2000  -> tolerance 20 to 100
  - larger answers    -> roughly 5% of the target
  Never exceed 50% of the target, or every guess wins.
- Good targets are counts and totals: career centuries, goals in a tournament,
  titles won, records held. Avoid numbers that shift with every fixture unless
  the context pins them to a stated date.
- Do NOT ask for a year — a year is a date, not a quantity, and tolerance
  ranges make no sense for it."""

SYSTEM_PROMPT = build_system_prompt(TYPE_RULES, factual=True)

GUESS_NUMBER_PROMPT = SYSTEM_PROMPT


@dataclass(frozen=True)
class GuessNumberTemplate:
    content_type: ContentType = ContentType.GUESS_NUMBER
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
            f"Write {count} guess-the-number item(s) now. Every target must be a "
            f"figure stated in the context.",
        ]
        return "\n\n".join(b for b in blocks if b)


TEMPLATE = GuessNumberTemplate()
