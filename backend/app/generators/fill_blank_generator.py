"""Fill-in-the-blank generator: one blank, four candidate fills."""

from __future__ import annotations

from pydantic import BaseModel

from app.generators.base import BaseGenerator
from app.retrieval.context_builder import ContextPack
from app.schemas.common import ContentType, Difficulty, Sport
from app.schemas.fill_blank import BLANK_TOKEN, FillBlankItem
from app.utils.helpers import normalize


class FillBlankGenerator(BaseGenerator):
    content_type = ContentType.FILL_BLANK

    def to_item(
        self,
        draft: BaseModel,
        *,
        sport: Sport,
        difficulty: Difficulty,
        context: ContextPack,
    ) -> FillBlankItem:
        correct = draft.options[draft.correct_index]

        # If the answer also appears elsewhere in the sentence, the blank is
        # self-solving.
        remainder = normalize(draft.sentence.replace(BLANK_TOKEN, " "))
        if normalize(correct) and normalize(correct) in remainder:
            raise ValueError("sentence repeats the answer outside the blank")

        return FillBlankItem(
            sport=sport,
            difficulty=difficulty,
            sentence=draft.sentence,
            options=list(draft.options),
            correct_index=draft.correct_index,
            explanation=draft.explanation,
            grounding=self._grounding_for(draft, context),
        )
