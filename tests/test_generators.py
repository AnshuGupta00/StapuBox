"""Per-type schema contracts, quality gates and the dedup loop.

The spec's hard rules live here: MCQ = 4 options + 1 correct, Poll = 2 options +
no correct answer, Guess-the-Number = target + tolerance range. Each is asserted
both at the schema layer (a bad draft must not construct) and at the generator
layer (a bad draft must not become an item).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.agent.freshness import NoveltyLedger
from app.generators import GENERATORS, get_generator
from app.retrieval.context_builder import ContextPack
from app.schemas.common import FACTUAL_TYPES, ContentType, Difficulty, Sport
from app.schemas.fill_blank import BLANK_TOKEN, FillBlankDraft
from app.schemas.guess_number import GuessNumberDraft, GuessNumberItem
from app.schemas.mcq import MCQDraft, MCQItem
from app.schemas.poll import PollDraft, PollItem
from app.schemas.true_false import TrueFalseDraft
from app.utils.validators import validate_item

SPORT = Sport.CRICKET
DIFFICULTY = Difficulty.MEDIUM


def generate_one(content_type: ContentType, ledger: NoveltyLedger | None = None, **kw):
    """Run a single type through the real generator loop in mock mode."""
    from app.agent.router import context_for, plan_retrieval, retrieve

    plan = plan_retrieval(content_types=[content_type], difficulty=DIFFICULTY)
    pack = retrieve(plan=plan, sport=SPORT, difficulty=DIFFICULTY)
    generator = get_generator(content_type)
    return generator.generate(
        sport=SPORT,
        difficulty=DIFFICULTY,
        count=kw.pop("count", 1),
        context=context_for(content_type, pack),
        novelty=ledger,
        require_grounding=content_type in FACTUAL_TYPES,
        **kw,
    )


# --------------------------------------------------------------------- registry


def test_every_content_type_has_a_generator():
    assert set(GENERATORS) == set(ContentType)


@pytest.mark.parametrize("content_type", list(ContentType))
def test_each_type_generates_a_valid_item(content_type: ContentType):
    result = generate_one(content_type)

    assert result.items, f"{content_type.value} produced nothing: {result.warnings}"
    item = result.items[0]
    assert item.content_type is content_type
    assert item.sport is SPORT

    errors, _ = validate_item(item, require_grounding=content_type in FACTUAL_TYPES)
    assert errors == []

    # Every item is packaged for Instagram and scored before it is returned.
    assert item.instagram is not None
    assert item.instagram.prompt_text
    assert 0 < item.engagement_score <= 100
    assert item.fingerprint


# ------------------------------------------------------------- per-type contract


def test_mcq_has_four_distinct_options_and_one_answer():
    item = generate_one(ContentType.MCQ).items[0]
    assert isinstance(item, MCQItem)
    assert len(item.options) == 4
    assert len({o.casefold() for o in item.options}) == 4
    assert 0 <= item.correct_index < 4
    assert item.correct_answer in item.options
    assert item.correct_letter in ("A", "B", "C", "D")
    # The answer must not be visible in the question.
    assert item.correct_answer.casefold() not in item.question.casefold()


def test_true_false_is_declarative_with_a_boolean_verdict():
    item = generate_one(ContentType.TRUE_FALSE).items[0]
    assert not item.statement.strip().endswith("?")
    assert isinstance(item.answer, bool)
    assert item.correct_answer in ("True", "False")


def test_poll_has_two_options_and_no_correct_answer():
    item = generate_one(ContentType.POLL).items[0]
    assert isinstance(item, PollItem)
    assert len(item.options) == 2
    assert item.correct_answer is None
    assert item.opinion_based is True
    # Opinion content is never fact-checked, and never claims a source.
    assert item.grounding.fact_checked is False
    assert item.grounding.resolved_sources == []


def test_fill_blank_has_exactly_one_blank_and_four_options():
    item = generate_one(ContentType.FILL_BLANK).items[0]
    assert item.sentence.count(BLANK_TOKEN) == 1
    assert len(item.options) == 4
    assert len({o.casefold() for o in item.options}) == 4
    correct = item.options[item.correct_index]
    # The blank must not be solvable by reading the rest of the sentence.
    assert correct.casefold() not in item.sentence.replace(BLANK_TOKEN, " ").casefold()


def test_guess_number_carries_a_usable_tolerance_range():
    item = generate_one(ContentType.GUESS_NUMBER).items[0]
    assert isinstance(item, GuessNumberItem)
    low, high = item.accepted_range
    assert low < item.target < high
    assert item.tolerance > 0
    assert item.tolerance <= abs(item.target) * 0.5
    assert item.is_accepted(item.target)
    assert item.is_accepted(high)
    assert not item.is_accepted(high + item.tolerance)
    assert "±" in item.range_label


# ------------------------------------------------------- draft schema rejections


def test_mcq_draft_rejects_wrong_option_count():
    with pytest.raises(ValidationError):
        MCQDraft(
            question="Q?", options=["a", "b", "c"], correct_index=0, explanation="e"
        )


def test_mcq_draft_rejects_duplicate_options():
    with pytest.raises(ValidationError):
        MCQDraft(
            question="Q?",
            options=["a", "A", "b", "c"],
            correct_index=0,
            explanation="e",
        )


def test_poll_draft_rejects_identical_options():
    with pytest.raises(ValidationError):
        PollDraft(prompt="This or that?", options=["Same", "same"])


def test_poll_item_cannot_declare_a_correct_answer():
    with pytest.raises(ValidationError):
        PollItem(
            sport=SPORT,
            difficulty=DIFFICULTY,
            prompt="A or B?",
            options=["A", "B"],
            correct_answer="A",
        )


def test_true_false_draft_rejects_a_question():
    with pytest.raises(ValidationError):
        TrueFalseDraft(
            statement="Did India win in 1983?", answer=True, explanation="e"
        )


def test_fill_blank_draft_rejects_two_blanks():
    with pytest.raises(ValidationError):
        FillBlankDraft(
            sentence=f"{BLANK_TOKEN} beat {BLANK_TOKEN} in the final.",
            options=["a", "b", "c", "d"],
            correct_index=0,
            explanation="e",
        )


def test_guess_number_draft_rejects_a_tolerance_that_swallows_the_answer():
    with pytest.raises(ValidationError):
        GuessNumberDraft(
            question="How many?", target=100, tolerance=60, explanation="e"
        )


# --------------------------------------------------------- generator-level gates


def test_mcq_generator_rejects_a_question_that_leaks_its_answer(grounded_pack):
    draft = MCQDraft(
        question="Did Australia win 6 World Cups?",
        options=["4", "5", "6", "7"],
        correct_index=2,
        explanation="e",
        cited_refs=["T1"],
    )
    generator = get_generator(ContentType.MCQ)
    with pytest.raises(ValueError, match="leaks"):
        generator.to_item(
            draft, sport=SPORT, difficulty=DIFFICULTY, context=grounded_pack
        )


def test_fill_blank_generator_rejects_a_self_solving_sentence(grounded_pack):
    draft = FillBlankDraft(
        sentence=f"India won the 1983 World Cup, so {BLANK_TOKEN} won in 1983.",
        options=["India", "Australia", "England", "Pakistan"],
        correct_index=0,
        explanation="e",
        cited_refs=["T1"],
    )
    generator = get_generator(ContentType.FILL_BLANK)
    with pytest.raises(ValueError):
        generator.to_item(
            draft, sport=SPORT, difficulty=DIFFICULTY, context=grounded_pack
        )


# -------------------------------------------------------- grounding and novelty


@pytest.mark.parametrize("content_type", sorted(FACTUAL_TYPES, key=lambda c: c.value))
def test_factual_types_refuse_to_generate_without_evidence(content_type: ContentType):
    """No evidence must mean no output — never an ungrounded guess."""
    generator = get_generator(content_type)
    result = generator.generate(
        sport=SPORT,
        difficulty=DIFFICULTY,
        count=2,
        context=ContextPack(),
        require_grounding=True,
    )
    assert result.items == []
    assert result.llm_calls == 0
    assert any("evidence" in w.lower() or "grounding" in w.lower() for w in result.warnings)


def test_polls_still_generate_without_evidence():
    """Opinion content needs no sources, so an empty pack must not block it."""
    generator = get_generator(ContentType.POLL)
    result = generator.generate(
        sport=SPORT, difficulty=DIFFICULTY, count=1, context=ContextPack()
    )
    assert len(result.items) == 1


def test_every_factual_item_resolves_at_least_one_source():
    for content_type in sorted(FACTUAL_TYPES, key=lambda c: c.value):
        item = generate_one(content_type).items[0]
        assert item.grounding.resolved_sources, content_type
        assert item.grounding.fact_checked is True
        assert item.grounding.cited_refs


def test_repeated_batches_do_not_repeat_facts(tmp_ledger: NoveltyLedger):
    """Freshness across requests: the ledger must block a second identical fact."""
    first = generate_one(ContentType.MCQ, ledger=tmp_ledger, count=3)
    second = generate_one(ContentType.MCQ, ledger=tmp_ledger, count=3)

    seen = {i.fingerprint for i in first.items}
    assert seen
    assert all(i.fingerprint not in seen for i in second.items)
    assert tmp_ledger.stats()["tracked"] == len(first.items) + len(second.items)


def test_duplicate_is_reported_not_silently_dropped(tmp_ledger: NoveltyLedger):
    item = generate_one(ContentType.MCQ, ledger=tmp_ledger).items[0]
    assert tmp_ledger.is_duplicate(item.fingerprint, text=item.dedup_text())


def test_avoid_list_steers_away_from_a_named_fact(tmp_ledger: NoveltyLedger):
    first = generate_one(ContentType.TRUE_FALSE, ledger=tmp_ledger).items[0]
    second = generate_one(
        ContentType.TRUE_FALSE, ledger=tmp_ledger, avoid=[first.dedup_text()]
    )
    assert second.items
    assert second.items[0].fingerprint != first.fingerprint
