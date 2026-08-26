"""Deterministic offline stand-in for the LLM.

Active whenever ``ANTHROPIC_API_KEY`` is absent or ``MOCK_LLM=1``. It produces
schema-valid drafts for all five content types from the seed corpus in
``data/raw`` (see :mod:`app.corpus`), so the dashboard, validators, dedup ledger
and API routes are all exercisable — and testable — without network access or
spend.

Every item generated here is reported with ``mock_mode=True`` in the response
diagnostics and a "mock" note in its grounding, so mock output can never be
mistaken for web-grounded content.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import TypeVar

from pydantic import BaseModel

from app.corpus import CORPUS_DIR, CorpusFact, load_corpus
from app.schemas.common import Source, SourceKind, Sport

logger = logging.getLogger(__name__)

TDraft = TypeVar("TDraft", bound=BaseModel)


@dataclass(frozen=True)
class Fact:
    """One verifiable fact, reshaped into all five content types."""

    question: str
    answer: str
    distractors: tuple[str, str, str]
    statement: str
    explanation: str
    number: float | None = None
    unit: str = ""

    def blank_sentence(self) -> str:
        """The declarative statement with the answer replaced by a blank."""
        if self.answer in self.statement:
            return self.statement.replace(self.answer, "____", 1)
        return f"{self.statement.rstrip('.')} — the answer is ____."


@dataclass(frozen=True)
class Debate:
    prompt: str
    left: str
    right: str


# ---------------------------------------------------------------------------
# The fact bank
#
# Facts and debates are loaded from ``data/raw/*.json`` through :mod:`app.corpus`
# — the same corpus the ChromaDB ingest script reads. Adding a fact there widens
# retrieval *and* the offline bank, which is what stops repeated offline batches
# from running out of unseen material.
#
# The tiny in-code fallback below only matters when the corpus files are absent
# (a checkout without ``data/``): mock mode still has to produce schema-valid
# content rather than fail.
# ---------------------------------------------------------------------------

_FALLBACK_FACTS: tuple[Fact, ...] = (
    Fact(
        "How many international centuries did Sachin Tendulkar score?",
        "100", ("94", "108", "112"),
        "Sachin Tendulkar scored 100 international centuries.",
        "Tendulkar finished with 100 international centuries — 51 in Tests and 49 in ODIs.",
        100, "centuries",
    ),
    Fact(
        "How many FIFA World Cups has Brazil won?",
        "5", ("3", "4", "6"),
        "Brazil have won 5 FIFA World Cups.",
        "Brazil won the World Cup in 1958, 1962, 1970, 1994 and 2002.",
        5, "titles",
    ),
    Fact(
        "How many Grand Slam singles titles did Serena Williams win?",
        "23", ("18", "21", "24"),
        "Serena Williams won 23 Grand Slam singles titles.",
        "Her 23 majors are the most by any player in the Open era.",
        23, "titles",
    ),
)

_GENERIC_DEBATES: tuple[Debate, ...] = (
    Debate("What matters more?", "Natural talent", "Relentless work"),
    Debate("Which era was stronger?", "Today's stars", "The old guard"),
    Debate("What decides a title?", "Peak individual", "Deepest squad"),
    Debate("Which is the better watch?", "Domestic league", "International"),
)


def _as_fact(record: CorpusFact) -> Fact:
    """Adapt a corpus record to the shape the draft builder needs.

    Distractors are padded rather than trusted blindly — an MCQ needs exactly
    three, and a hand-edited corpus record may carry fewer.
    """
    distractors = [d for d in record.distractors if d and d != record.answer][:3]
    for filler in ("Not recorded", "None of these", "Unknown"):
        if len(distractors) >= 3:
            break
        if filler != record.answer:
            distractors.append(filler)
    return Fact(
        question=record.question,
        answer=record.answer,
        distractors=(distractors[0], distractors[1], distractors[2]),
        statement=record.statement,
        explanation=record.explanation or record.statement,
        number=record.number,
        unit=record.unit,
    )


@lru_cache(maxsize=1)
def _bank() -> tuple[dict[Sport, tuple[Fact, ...]], dict[Sport, tuple[Debate, ...]]]:
    """Build (and cache) the offline bank from the seed corpus."""
    corpus = load_corpus()
    facts = {
        sport: tuple(_as_fact(record) for record in records)
        for sport, records in corpus.facts.items()
        if records
    }
    debates = {
        sport: tuple(Debate(d.prompt, d.left, d.right) for d in records)
        for sport, records in corpus.debates.items()
        if records
    }
    if not facts:
        logger.warning(
            "No seed corpus under %s — mock mode is using a three-fact fallback. "
            "Restore data/raw/*.json for realistic offline output.",
            CORPUS_DIR,
        )
    return facts, debates


def reset_bank() -> None:
    """Drop the cached bank. Used by tests that point at a temporary corpus."""
    _bank.cache_clear()


# Rotating offset so successive requests surface different facts, mirroring the
# freshness behaviour of the live agent.
_rotation = 0


def reset_rotation() -> None:
    """Reset the rotation counter. Used by tests for determinism."""
    global _rotation
    _rotation = 0


def _advance() -> int:
    global _rotation
    current = _rotation
    _rotation += 1
    return current


def _sport_from_prompt(prompt: str) -> Sport:
    match = re.search(r"^SPORT:\s*(.+)$", prompt, re.MULTILINE)
    if match:
        raw = match.group(1).strip()
        for sport in Sport:
            if sport.value.casefold() == raw.casefold():
                return sport
    return Sport.CRICKET


def _facts_for(sport: Sport) -> tuple[Fact, ...]:
    """Facts for a sport, with graceful degradation to *something* usable."""
    facts, _ = _bank()
    if sport in facts:
        return facts[sport]
    if facts:
        return facts.get(Sport.CRICKET) or next(iter(facts.values()))
    return _FALLBACK_FACTS


def _debates_for(sport: Sport) -> tuple[Debate, ...]:
    _, debates = _bank()
    return debates.get(sport) or _GENERIC_DEBATES


def _tolerance_for(value: float) -> float:
    """Pick a tolerance that scales with the magnitude of the answer."""
    magnitude = abs(value)
    if magnitude == 0:
        return 1
    if not float(value).is_integer():
        return max(round(magnitude * 0.02, 2), 0.05)
    if magnitude < 20:
        return 1
    if magnitude < 200:
        return 5
    if magnitude < 2000:
        return 25
    return round(magnitude * 0.05)


def mock_research(*, sport: Sport, topic: str = "") -> tuple[str, list[Source]]:
    """Fabricate a research digest from the local fact bank.

    Returns ``(notes, sources)``. Sources are flagged as vector-DB style rather
    than web search, because nothing was actually fetched.
    """
    facts = _facts_for(sport)
    lines = [f"FACT: {fact.statement} {fact.explanation}" for fact in facts]
    header = f"[MOCK MODE] Offline sample facts for {sport.value}"
    if topic.strip():
        header += f" (requested focus: {topic.strip()})"
    notes = header + "\n" + "\n".join(lines)
    sources = [
        Source(
            ref=f"M{i + 1}",
            kind=SourceKind.VECTOR_DB,
            title=f"Offline sample fact — {sport.value}",
            snippet=fact.statement,
        )
        for i, fact in enumerate(facts)
    ]
    return notes, sources


def mock_drafts(
    *, draft_cls: type[TDraft], count: int, user_prompt: str = ""
) -> list[TDraft]:
    """Build ``count`` schema-valid drafts of the requested type."""
    from app.schemas.fill_blank import FillBlankDraft
    from app.schemas.guess_number import GuessNumberDraft
    from app.schemas.mcq import MCQDraft
    from app.schemas.poll import PollDraft
    from app.schemas.true_false import TrueFalseDraft

    sport = _sport_from_prompt(user_prompt)
    offset = _advance()

    if draft_cls is PollDraft:
        debates = _debates_for(sport)
        polls: list[BaseModel] = []
        for i in range(count):
            debate = debates[(offset + i) % len(debates)]
            polls.append(
                PollDraft(
                    prompt=debate.prompt,
                    options=[debate.left, debate.right],
                    rationale="[MOCK] Fans split on this one; there is no right answer.",
                )
            )
        return polls  # type: ignore[return-value]

    facts = _facts_for(sport)
    if draft_cls is GuessNumberDraft:
        numeric = [f for f in facts if f.number is not None] or list(facts)
        drafts: list[BaseModel] = []
        for i in range(count):
            fact = numeric[(offset + i) % len(numeric)]
            target = float(fact.number if fact.number is not None else 1)
            drafts.append(
                GuessNumberDraft(
                    question=fact.question,
                    target=target,
                    tolerance=_tolerance_for(target),
                    unit=fact.unit,
                    explanation=f"[MOCK] {fact.explanation}",
                    cited_refs=[f"M{facts.index(fact) + 1}"],
                    confidence="medium",
                )
            )
        return drafts  # type: ignore[return-value]

    drafts = []
    for i in range(count):
        index = (offset + i) % len(facts)
        fact = facts[index]
        ref = [f"M{index + 1}"]

        if draft_cls is MCQDraft:
            options = [fact.distractors[0], fact.answer, fact.distractors[1], fact.distractors[2]]
            # Rotate the answer position so it is not always index 1.
            shift = (offset + i) % 4
            options = options[shift:] + options[:shift]
            drafts.append(
                MCQDraft(
                    question=fact.question,
                    options=options,
                    correct_index=options.index(fact.answer),
                    explanation=f"[MOCK] {fact.explanation}",
                    cited_refs=ref,
                    confidence="medium",
                )
            )
        elif draft_cls is TrueFalseDraft:
            # Alternate verdicts; build the false variant by swapping one detail.
            make_true = (offset + i) % 2 == 0
            if make_true:
                statement, answer = fact.statement, True
            else:
                statement = fact.statement.replace(fact.answer, fact.distractors[0], 1)
                answer = False
                if statement == fact.statement:  # answer not present verbatim
                    statement, answer = fact.statement, True
            drafts.append(
                TrueFalseDraft(
                    statement=statement,
                    answer=answer,
                    explanation=f"[MOCK] {fact.explanation}",
                    cited_refs=ref,
                    confidence="medium",
                )
            )
        elif draft_cls is FillBlankDraft:
            options = [fact.answer, *fact.distractors]
            shift = (offset + i) % 4
            options = options[shift:] + options[:shift]
            drafts.append(
                FillBlankDraft(
                    sentence=fact.blank_sentence(),
                    options=options,
                    correct_index=options.index(fact.answer),
                    explanation=f"[MOCK] {fact.explanation}",
                    cited_refs=ref,
                    confidence="medium",
                )
            )
        else:  # pragma: no cover - every registered type is handled above
            raise ValueError(f"No mock generator for {draft_cls.__name__}")

    return drafts  # type: ignore[return-value]
