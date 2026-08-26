"""Fill-in-the-blank generation template."""

from __future__ import annotations

from dataclasses import dataclass

from app.prompts.base import (
    build_system_prompt,
    render_avoid_block,
    render_context_block,
    render_task_header,
)
from app.schemas.common import ContentType, Difficulty, Sport
from app.schemas.fill_blank import BLANK_TOKEN

TYPE_RULES = f"""\
FORMAT — FILL IN THE BLANK:
- One factual sentence with EXACTLY ONE blank, written as `{BLANK_TOKEN}`
  (four underscores). Never use a different marker and never use two blanks.
- Provide exactly FOUR options; `correct_index` is the zero-based position of
  the one that correctly completes the sentence.
- Blank out the single most interesting term — the player, number, team, venue
  or year the sentence is really about. Never blank a filler word.
- The sentence must read naturally once filled, and must give enough context to
  be solvable. Put the blank mid-sentence rather than at the very start.
- All four options must fit the blank grammatically, so the answer cannot be
  found by reading for grammar alone."""

SYSTEM_PROMPT = build_system_prompt(TYPE_RULES, factual=True)

FILL_BLANK_PROMPT = SYSTEM_PROMPT


@dataclass(frozen=True)
class FillBlankTemplate:
    content_type: ContentType = ContentType.FILL_BLANK
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
            f"Write {count} fill-in-the-blank item(s) now. "
            f"Use `{BLANK_TOKEN}` for the blank.",
        ]
        return "\n\n".join(b for b in blocks if b)


TEMPLATE = FillBlankTemplate()
