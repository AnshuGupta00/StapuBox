"""Retrieval, grounding and corpus quality.

Three things are checked here: the seed corpus is fit to become quiz content,
citation handles resolve only to evidence we really retrieved, and the retrieval
router makes the right call per request shape.
"""

from __future__ import annotations

import pytest

from app.agent.router import KB_RESULTS, context_for, plan_retrieval, retrieve, to_report
from app.config import Settings
from app.corpus import load_corpus
from app.retrieval.chroma_client import KnowledgeBase
from app.retrieval.context_builder import ContextPack, build_context, opinion_context
from app.schemas.common import (
    ContentType,
    Difficulty,
    Source,
    SourceKind,
    Sport,
)
from app.services.citation_service import build_grounding, citation_labels
from app.utils.helpers import content_key, fingerprint, jaccard, normalize

CORPUS = load_corpus()


# ------------------------------------------------------------------ seed corpus


def test_corpus_is_seeded_for_every_sport():
    assert not CORPUS.is_empty
    assert CORPUS.total_facts >= 50
    missing = [s.value for s in Sport if not CORPUS.facts_for(s)]
    assert missing == [], f"no seed facts for: {missing}"


@pytest.mark.parametrize("sport", list(Sport))
def test_every_sport_has_enough_material_for_a_batch(sport: Sport):
    # A batch of five draws from one sport; a thin bank would force duplicates.
    assert len(CORPUS.facts_for(sport)) >= 5
    assert len(CORPUS.debates_for(sport)) >= 4


def test_every_fact_can_become_all_five_formats():
    """The corpus is the offline draft bank, so each record must satisfy the
    same contracts the generators enforce."""
    problems: list[str] = []
    for fact in CORPUS.all_facts():
        label = f"{fact.sport.value}: {fact.question[:48]}"
        options = [fact.answer, *fact.distractors]

        if len(fact.distractors) != 3:
            problems.append(f"{label} -> {len(fact.distractors)} distractors")
        if len({normalize(o) for o in options}) != len(options):
            problems.append(f"{label} -> options not distinct")
        if normalize(fact.answer) in normalize(fact.question):
            problems.append(f"{label} -> question leaks the answer")
        if not fact.statement or fact.statement.strip().endswith("?"):
            problems.append(f"{label} -> statement is not declarative")
        if not fact.explanation:
            problems.append(f"{label} -> no explanation")

        # Fill-in-the-blank blanks the first occurrence of the answer, so the
        # answer must not appear a second time anywhere in the statement.
        blanked = fact.statement.replace(fact.answer, " ", 1)
        if normalize(fact.answer) in normalize(blanked):
            problems.append(f"{label} -> statement repeats the answer")

    assert problems == []


def test_numeric_facts_are_usable_as_guess_the_number():
    numeric = [f for f in CORPUS.all_facts() if f.number is not None]
    assert len(numeric) >= 30
    for fact in numeric:
        assert fact.number != 0, fact.question
        # Years make terrible guess-the-number targets and are excluded by the
        # generator, so they must not be stored as numbers.
        assert not (1800 < fact.number < 2100 and fact.unit == ""), fact.question


def test_doc_ids_are_unique_and_stable():
    ids = [f.doc_id() for f in CORPUS.all_facts()]
    assert len(ids) == len(set(ids))
    first = CORPUS.all_facts()[0]
    assert first.doc_id() == first.doc_id()
    assert first.sport.value.lower().replace(" ", "-") in first.doc_id()
    assert first.statement in first.document()
    assert first.metadata()["sport"] == first.sport.value


def test_no_two_facts_share_a_fingerprint():
    """Two facts with the same dedup key would collide in the novelty ledger."""
    keys = [fingerprint(f"{f.question} :: {f.answer}") for f in CORPUS.all_facts()]
    assert len(keys) == len(set(keys))


# ------------------------------------------------------------------- citations


def test_resolve_keeps_real_handles_and_drops_invented_ones():
    pack = ContextPack(
        sources=[
            Source(ref="W1", kind=SourceKind.WEB_SEARCH, title="Real result"),
            Source(ref="K1", kind=SourceKind.VECTOR_DB, title="Real doc"),
        ]
    )
    resolved = pack.resolve(["W1", "W9", "k1", "K1"])
    assert [s.ref for s in resolved] == ["W1", "K1"]  # deduped, case-insensitive


def test_grounding_is_false_when_every_handle_is_invented():
    pack = ContextPack(sources=[Source(ref="W1", kind=SourceKind.WEB_SEARCH)])
    grounding = build_grounding(
        content_type=ContentType.MCQ,
        cited_refs=["W7"],
        context=pack,
        confidence="high",
    )
    assert grounding.is_grounded is False
    assert grounding.fact_checked is False
    # An ungrounded item may never keep a high confidence claim.
    assert grounding.confidence == "low"


def test_grounding_describes_which_backend_supported_the_answer():
    pack = ContextPack(
        sources=[
            Source(ref="W1", kind=SourceKind.WEB_SEARCH, title="ESPN"),
            Source(ref="K1", kind=SourceKind.VECTOR_DB, title="KB entry"),
        ]
    )
    grounding = build_grounding(
        content_type=ContentType.MCQ, cited_refs=["W1", "K1"], context=pack
    )
    assert grounding.is_grounded
    assert "web search" in grounding.reasoning
    assert "knowledge base" in grounding.reasoning
    labels = citation_labels(grounding)
    assert labels[0].startswith("W1 · Web search")
    assert labels[1].startswith("K1 · Knowledge base")


def test_polls_are_never_fact_checked_even_if_they_cite():
    pack = ContextPack(sources=[Source(ref="W1", kind=SourceKind.WEB_SEARCH)])
    grounding = build_grounding(
        content_type=ContentType.POLL, cited_refs=["W1"], context=pack
    )
    assert grounding.fact_checked is False
    assert grounding.resolved_sources == []
    assert "opinion" in grounding.reasoning.lower()


# ----------------------------------------------------------------- the router


def test_opinion_only_batches_skip_web_search():
    plan = plan_retrieval(content_types=[ContentType.POLL], difficulty=Difficulty.EASY)
    assert plan.use_web_search is False
    assert any("opinion-only" in r.lower() for r in plan.reasons)


def test_a_topic_forces_web_search_even_for_polls():
    plan = plan_retrieval(
        content_types=[ContentType.POLL],
        difficulty=Difficulty.EASY,
        topic="Ashes 2025",
    )
    assert plan.use_web_search is True
    assert any("Ashes 2025" in r for r in plan.reasons)


def test_hard_difficulty_widens_the_knowledge_base_sweep():
    easy = plan_retrieval(content_types=[ContentType.MCQ], difficulty=Difficulty.EASY)
    hard = plan_retrieval(content_types=[ContentType.MCQ], difficulty=Difficulty.HARD)
    assert hard.kb_results > easy.kb_results
    assert hard.kb_results == KB_RESULTS[Difficulty.HARD]


def test_web_search_can_be_disabled_by_configuration():
    settings = Settings()
    settings.enable_web_search = False
    plan = plan_retrieval(
        content_types=[ContentType.MCQ],
        difficulty=Difficulty.MEDIUM,
        settings=settings,
    )
    assert plan.use_web_search is False
    assert any("configuration" in r for r in plan.reasons)


def test_caller_can_turn_web_search_off_per_request():
    plan = plan_retrieval(
        content_types=[ContentType.MCQ],
        difficulty=Difficulty.MEDIUM,
        requested_web_search=False,
    )
    assert plan.use_web_search is False


# ---------------------------------------------------------------- context pack


def test_offline_context_pack_is_citable():
    """Mock-mode evidence keeps its own handles so its citations still resolve."""
    pack = build_context(sport=Sport.CRICKET, difficulty=Difficulty.MEDIUM)
    assert pack.sources
    assert pack.research_notes
    refs = [s.ref for s in pack.sources]
    assert any(r.startswith("M") for r in refs)
    assert pack.resolve([refs[0]])
    assert pack.web_used is False  # no key configured in tests
    assert not pack.is_empty


def test_empty_knowledge_base_degrades_with_an_actionable_message():
    pack = build_context(sport=Sport.CHESS, difficulty=Difficulty.EASY)
    assert pack.vector_hits == 0  # tests use a throwaway Chroma directory
    assert any("ingest_data" in m for m in pack.messages)


def test_opinion_context_carries_no_resolvable_factual_source():
    pack = build_context(sport=Sport.FOOTBALL, difficulty=Difficulty.MEDIUM)
    trimmed = opinion_context(pack)
    assert [s.ref for s in trimmed.sources] == ["OPINION"]
    assert trimmed.resolve(["M1", "W1", "K1"]) == []


def test_context_for_routes_polls_to_the_opinion_pack():
    pack = build_context(sport=Sport.TENNIS, difficulty=Difficulty.MEDIUM)
    poll_ctx = context_for(ContentType.POLL, pack)
    mcq_ctx = context_for(ContentType.MCQ, pack)
    assert [s.kind for s in poll_ctx.sources] == [SourceKind.OPINION]
    assert mcq_ctx is pack


def test_retrieval_report_explains_what_was_used():
    plan = plan_retrieval(content_types=[ContentType.MCQ], difficulty=Difficulty.HARD)
    pack = retrieve(plan=plan, sport=Sport.CRICKET, difficulty=Difficulty.HARD)
    report = to_report(pack)
    assert report.messages, "the report must say what retrieval did"
    assert report.sources
    assert any("knowledge base sweep" in m for m in report.messages)


# ------------------------------------------------------------- the vector store


def test_knowledge_base_round_trip():
    kb = KnowledgeBase()
    if not kb.available:
        pytest.skip(f"ChromaDB unavailable: {kb.unavailable_reason}")

    before = kb.count()
    written = kb.upsert(
        [
            {
                "id": "test-doc-1",
                "text": "The Ranji Trophy is India's premier first-class competition.",
                "sport": Sport.CRICKET.value,
                "title": "Ranji Trophy",
            },
            {
                "id": "test-doc-2",
                "text": "The Davis Cup is the premier men's international team tennis event.",
                "sport": Sport.TENNIS.value,
                "title": "Davis Cup",
            },
        ]
    )
    assert written == 2
    assert kb.count() == before + 2

    hits = kb.query(text="first-class cricket competition", sport=Sport.CRICKET)
    assert hits, "expected a semantic hit for the ingested cricket document"
    assert hits[0].ref == "K1"
    assert hits[0].kind is SourceKind.VECTOR_DB
    assert "Ranji" in hits[0].snippet

    # The sport filter must not leak documents across sports.
    assert all("Davis Cup" not in h.snippet for h in hits)

    # start_ref offsets handles so they never collide with web handles.
    offset = kb.query(text="tennis team event", sport=Sport.TENNIS, start_ref=3)
    assert offset and offset[0].ref == "K4"

    # Re-upserting the same ids updates instead of duplicating.
    kb.upsert([{"id": "test-doc-1", "text": "Updated text.", "sport": Sport.CRICKET.value}])
    assert kb.count() == before + 2


# --------------------------------------------------------------- text helpers


def test_content_key_ignores_word_order_and_stopwords():
    a = content_key("Who won the 1983 World Cup?")
    b = content_key("The 1983 World Cup was won by whom?")
    assert a == b
    assert fingerprint("Who won the 1983 World Cup?") == fingerprint(
        "The 1983 World Cup was won by whom?"
    )


def test_jaccard_scores_near_duplicates_high():
    close = jaccard(
        "How many Test wickets did Muralitharan take?",
        "How many wickets did Muttiah Muralitharan take in Tests?",
    )
    far = jaccard(
        "How many Test wickets did Muralitharan take?",
        "Which team won the 2024 NBA championship?",
    )
    assert close > far
    assert 0.0 <= far < 0.2
