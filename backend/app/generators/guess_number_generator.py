"""Guess-the-number generator: a numeric target plus an accepted range."""

from __future__ import annotations

import re

from pydantic import BaseModel

from app.generators.base import BaseGenerator
from app.retrieval.context_builder import ContextPack
from app.schemas.common import ContentType, Difficulty, Sport
from app.schemas.guess_number import GuessNumberItem

_YEAR_QUESTION = re.compile(r"\b(what|which|in what)\s+year\b", re.IGNORECASE)


class GuessNumberGenerator(BaseGenerator):
    content_type = ContentType.GUESS_NUMBER

    def to_item(
        self,
        draft: BaseModel,
        *,
        sport: Sport,
        difficulty: Difficulty,
        context: ContextPack,
    ) -> GuessNumberItem:
        # A year has no meaningful tolerance — "1983 ±5" accepts a decade of
        # wrong answers, so these belong in an MCQ instead.
        if _YEAR_QUESTION.search(draft.question) or (
            1800 <= draft.target <= 2200 and "year" in draft.question.casefold()
        ):
            raise ValueError("year questions are not valid guess-the-number items")

        # With a target of zero, tolerance is unbounded relative to magnitude.
        if draft.target == 0:
            raise ValueError("target must be non-zero")

        if float(draft.target).is_integer() and str(int(draft.target)) in draft.question:
            raise ValueError("question states the answer")

        return GuessNumberItem(
            sport=sport,
            difficulty=difficulty,
            question=draft.question,
            target=draft.target,
            tolerance=draft.tolerance,
            unit=draft.unit,
            explanation=draft.explanation,
            grounding=self._grounding_for(draft, context),
        )
