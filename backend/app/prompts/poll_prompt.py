"""This-or-That poll template. The only opinion-based type."""

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
FORMAT — THIS-OR-THAT POLL:
- Exactly TWO options. No correct answer. Never include one.
- The prompt names both sides and the axis of comparison, so the debate is
  specific: "Messi or Ronaldo — who's the greater dribbler?" beats
  "Messi or Ronaldo?".
- Pick a genuinely contested axis. Comparing an all-time great to a journeyman
  is not a poll, it is a formality.
- Options should be short labels — usually just the two names.
- Range across the batch: all-time-great debates, current form, tactical
  preferences, format arguments, era-vs-era. Do not write five GOAT questions.
- `rationale` explains why fans split. It must not pick a winner."""

SYSTEM_PROMPT = build_system_prompt(TYPE_RULES, factual=False)

POLL_PROMPT = SYSTEM_PROMPT


@dataclass(frozen=True)
class PollTemplate:
    content_type: ContentType = ContentType.POLL
    system: str = SYSTEM_PROMPT
    factual: bool = False

    def render_user(
        self,
        *,
        sport: Sport,
        difficulty: Difficulty | None,
        count: int,
        topic: str,
        context_text: str,
        recent: list[str],
    ) -> str:
        # Difficulty is intentionally dropped: an opinion poll has no
        # difficulty, and passing one nudges the model toward trivia.
        blocks = [
            render_task_header(
                sport=sport, difficulty=None, count=count, topic=topic
            ),
            render_context_block(context_text),
            render_avoid_block(recent),
            f"Write {count} this-or-that poll(s) now. No correct answers.",
        ]
        return "\n\n".join(b for b in blocks if b)


TEMPLATE = PollTemplate()
