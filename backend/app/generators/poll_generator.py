"""This-or-That poll generator: two sides, no right answer.

The only opinion-based type. It deliberately does not resolve citations — the
``rationale`` is framing for the creator, never a verdict, and the item is
returned with ``fact_checked=False``.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.generators.base import BaseGenerator
from app.retrieval.context_builder import ContextPack
from app.schemas.common import ContentType, Difficulty, Sport
from app.schemas.poll import PollItem

#: A this-or-that needs two *named* sides. Yes/no turns it into a survey and
#: kills the debate the format exists to create.
_BANNED_OPTIONS = {"yes", "no", "agree", "disagree", "true", "false", "both", "neither"}


class PollGenerator(BaseGenerator):
    content_type = ContentType.POLL

    def to_item(
        self,
        draft: BaseModel,
        *,
        sport: Sport,
        difficulty: Difficulty,
        context: ContextPack,
    ) -> PollItem:
        for option in draft.options:
            if option.strip().casefold() in _BANNED_OPTIONS:
                raise ValueError(f"'{option}' is not a this-or-that side")

        return PollItem(
            sport=sport,
            difficulty=difficulty,
            prompt=draft.prompt,
            options=list(draft.options),
            # The rationale explains why fans split — it is never an answer.
            explanation=draft.rationale,
            grounding=self._grounding_for(draft, context),
        )
