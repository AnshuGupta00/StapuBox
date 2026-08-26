"""True/False generator: a declarative statement plus its verdict."""

from __future__ import annotations

from pydantic import BaseModel

from app.generators.base import BaseGenerator
from app.retrieval.context_builder import ContextPack
from app.schemas.common import ContentType, Difficulty, Sport
from app.schemas.true_false import TrueFalseItem

#: Hedges make a statement unfalsifiable, so the verdict becomes a coin flip.
_HEDGES = (
    "arguably",
    "possibly",
    "some people",
    "many believe",
    "widely considered",
    "one of the best",
    "probably",
)


class TrueFalseGenerator(BaseGenerator):
    content_type = ContentType.TRUE_FALSE

    def to_item(
        self,
        draft: BaseModel,
        *,
        sport: Sport,
        difficulty: Difficulty,
        context: ContextPack,
    ) -> TrueFalseItem:
        lowered = draft.statement.casefold()
        hedge = next((h for h in _HEDGES if h in lowered), None)
        if hedge:
            raise ValueError(f"statement is subjective (contains '{hedge}')")

        return TrueFalseItem(
            sport=sport,
            difficulty=difficulty,
            statement=draft.statement,
            answer=draft.answer,
            explanation=draft.explanation,
            grounding=self._grounding_for(draft, context),
        )
