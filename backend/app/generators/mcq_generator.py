"""MCQ generator: 4 options, exactly 1 correct."""

from __future__ import annotations

from pydantic import BaseModel

from app.generators.base import BaseGenerator
from app.retrieval.context_builder import ContextPack
from app.schemas.common import ContentType, Difficulty, Sport
from app.schemas.mcq import MCQItem
from app.utils.helpers import normalize


class MCQGenerator(BaseGenerator):
    content_type = ContentType.MCQ

    def to_item(
        self,
        draft: BaseModel,
        *,
        sport: Sport,
        difficulty: Difficulty,
        context: ContextPack,
    ) -> MCQItem:
        correct = draft.options[draft.correct_index]

        # A question that already contains its own answer is not a quiz.
        if normalize(correct) and normalize(correct) in normalize(draft.question):
            raise ValueError("question leaks the correct option")

        return MCQItem(
            sport=sport,
            difficulty=difficulty,
            question=draft.question,
            options=list(draft.options),
            correct_index=draft.correct_index,
            explanation=draft.explanation,
            grounding=self._grounding_for(draft, context),
        )
