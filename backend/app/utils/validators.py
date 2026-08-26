"""Post-schema validation.

Pydantic already guarantees each item's *shape* (four options, one blank, a
positive tolerance). This module enforces the rules that shape alone cannot
express:

* a factual item must resolve to at least one real retrieved source;
* an opinion poll must never be marked fact-checked or carry a correct answer;
* the correct answer must actually be reachable from the options;
* copy should fit Instagram's sticker budgets.

:func:`validate_item` returns ``(blocking_errors, warnings)``. Blocking errors
cause the item to be rejected and regenerated; warnings are surfaced to the
dashboard but do not discard otherwise good content.
"""

from __future__ import annotations

from app.schemas.common import FACTUAL_TYPES, ContentType
from app.schemas.base import BaseItem
from app.schemas.fill_blank import BLANK_TOKEN, FillBlankItem
from app.schemas.guess_number import GuessNumberItem
from app.schemas.mcq import MCQItem
from app.schemas.poll import PollItem
from app.schemas.true_false import TrueFalseItem

#: Recommended character budgets for Instagram's native tools. These are
#: conservative guideline values, not API-enforced limits — Instagram truncates
#: silently, so staying inside them keeps copy fully visible. Tune freely.
INSTAGRAM_LIMITS = {
    "prompt": 92,
    "option": 24,
    "caption": 2200,
}


def validate_item(
    item: BaseItem, *, require_grounding: bool = True
) -> tuple[list[str], list[str]]:
    """Validate one item. Returns ``(errors, warnings)``."""
    errors: list[str] = []
    warnings: list[str] = []

    _check_grounding(item, errors, warnings, require_grounding=require_grounding)
    _check_type_rules(item, errors, warnings)
    _check_lengths(item, warnings)

    return errors, warnings


def _check_grounding(
    item: BaseItem,
    errors: list[str],
    warnings: list[str],
    *,
    require_grounding: bool,
) -> None:
    is_factual = item.content_type in FACTUAL_TYPES

    if not is_factual:
        # Opinion content must never claim fact-checked status.
        if item.grounding.fact_checked:
            errors.append("opinion content must not be marked fact-checked")
        if item.grounding.resolved_sources:
            warnings.append("opinion content carries factual sources; ignoring them")
        return

    if not item.grounding.resolved_sources:
        message = (
            "no retrieved source supports this item "
            f"(claimed refs: {item.grounding.cited_refs or 'none'})"
        )
        if require_grounding:
            errors.append(message)
        else:
            warnings.append(message)

    unresolved = len(item.grounding.cited_refs) - len(item.grounding.resolved_sources)
    if unresolved > 0:
        warnings.append(f"{unresolved} cited reference(s) did not match any source")

    if item.grounding.confidence == "low":
        warnings.append("model reported low confidence in this fact")


def _check_type_rules(
    item: BaseItem, errors: list[str], warnings: list[str]
) -> None:
    if isinstance(item, MCQItem):
        if len(item.options) != 4:
            errors.append("MCQ must have exactly 4 options")
        if len({o.strip().casefold() for o in item.options}) != len(item.options):
            errors.append("MCQ options must be distinct")
        if not 0 <= item.correct_index < len(item.options):
            errors.append("MCQ correct_index is out of range")

    elif isinstance(item, PollItem):
        if len(item.options) != 2:
            errors.append("Poll must have exactly 2 options")
        if item.correct_answer is not None:
            errors.append("Poll must not declare a correct answer")
        if item.options[0].strip().casefold() == item.options[1].strip().casefold():
            errors.append("Poll options must differ")

    elif isinstance(item, FillBlankItem):
        if item.sentence.count(BLANK_TOKEN) != 1:
            errors.append(f"fill-in-the-blank needs exactly one '{BLANK_TOKEN}'")
        if len(item.options) != 4:
            errors.append("fill-in-the-blank must have exactly 4 options")
        if len({o.strip().casefold() for o in item.options}) != len(item.options):
            errors.append("fill-in-the-blank options must be distinct")

    elif isinstance(item, GuessNumberItem):
        if item.tolerance <= 0:
            errors.append("guess-the-number needs a positive tolerance")
        elif abs(item.target) > 0 and item.tolerance > abs(item.target) * 0.5:
            errors.append("tolerance too wide — every guess would be accepted")
        low, high = item.accepted_range
        if low > high:
            errors.append("accepted range is inverted")

    elif isinstance(item, TrueFalseItem):
        if item.statement.strip().endswith("?"):
            errors.append("True/False needs a declarative statement, not a question")

    if item.content_type in FACTUAL_TYPES and not item.explanation.strip():
        warnings.append("missing explanation")


def _check_lengths(item: BaseItem, warnings: list[str]) -> None:
    payload = item.instagram
    if payload is None:
        return
    if len(payload.prompt_text) > INSTAGRAM_LIMITS["prompt"]:
        warnings.append(
            f"prompt is {len(payload.prompt_text)} chars; "
            f"Instagram shows about {INSTAGRAM_LIMITS['prompt']}"
        )
    for option in payload.option_texts:
        if len(option) > INSTAGRAM_LIMITS["option"]:
            warnings.append(
                f"option '{option[:18]}…' is {len(option)} chars; "
                f"keep options under {INSTAGRAM_LIMITS['option']}"
            )


def summarize_batch(items: list[BaseItem]) -> dict[str, int]:
    """Type histogram for the dashboard."""
    counts = {ct.value: 0 for ct in ContentType}
    for item in items:
        counts[item.content_type.value] += 1
    return counts
