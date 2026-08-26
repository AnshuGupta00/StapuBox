"""The seed knowledge corpus — one source of truth, two consumers.

``data/raw/*.json`` holds hand-checked, settled sports facts. Two very different
parts of the system read them:

* :mod:`scripts.ingest_data` turns each record into a ChromaDB document, so
  retrieval can ground historical questions;
* :mod:`app.services.mock_llm` reshapes the same records into offline drafts, so
  the dashboard works before an API key exists.

Keeping one corpus means adding a fact improves retrieval *and* the offline demo,
and the two can never drift apart. Each record carries the pieces every content
type needs — a question, its answer, three plausible distractors, a declarative
statement and an explanation — because deriving good distractors from a bare
sentence is exactly the kind of guessing that produces hallucinations.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from app.config import PROJECT_ROOT
from app.schemas.common import Sport
from app.utils.helpers import fingerprint

logger = logging.getLogger(__name__)

#: Where the seed files live.
CORPUS_DIR = PROJECT_ROOT / "data" / "raw"

_SPORT_BY_VALUE = {s.value.casefold(): s for s in Sport}


@dataclass(frozen=True)
class CorpusFact:
    """One verified fact, rich enough to become any of the five formats."""

    sport: Sport
    question: str
    answer: str
    distractors: tuple[str, ...]
    statement: str
    explanation: str
    number: float | None = None
    unit: str = ""
    tags: tuple[str, ...] = ()

    def document(self) -> str:
        """The text embedded into the vector DB."""
        return f"{self.statement} {self.explanation}".strip()

    def doc_id(self) -> str:
        """Stable id so re-ingesting updates rather than duplicates."""
        return f"{self.sport.value.lower().replace(' ', '-')}-{fingerprint(self.statement)}"

    def metadata(self) -> dict[str, str]:
        return {
            "sport": self.sport.value,
            "answer": self.answer,
            "tags": ",".join(self.tags),
            "unit": self.unit,
        }


@dataclass(frozen=True)
class CorpusDebate:
    """A this-or-that hook: two named sides, no right answer."""

    sport: Sport
    prompt: str
    left: str
    right: str


@dataclass
class Corpus:
    facts: dict[Sport, tuple[CorpusFact, ...]] = field(default_factory=dict)
    debates: dict[Sport, tuple[CorpusDebate, ...]] = field(default_factory=dict)
    source_files: tuple[str, ...] = ()

    @property
    def total_facts(self) -> int:
        return sum(len(v) for v in self.facts.values())

    @property
    def total_debates(self) -> int:
        return sum(len(v) for v in self.debates.values())

    def all_facts(self) -> list[CorpusFact]:
        return [f for facts in self.facts.values() for f in facts]

    def facts_for(self, sport: Sport) -> tuple[CorpusFact, ...]:
        return self.facts.get(sport, ())

    def debates_for(self, sport: Sport) -> tuple[CorpusDebate, ...]:
        return self.debates.get(sport, ())

    @property
    def is_empty(self) -> bool:
        return not self.facts


def _parse_sport(raw: str) -> Sport | None:
    return _SPORT_BY_VALUE.get(str(raw).strip().casefold())


def _parse_fact(sport: Sport, raw: dict) -> CorpusFact | None:
    question = str(raw.get("question", "")).strip()
    answer = str(raw.get("answer", "")).strip()
    statement = str(raw.get("statement", "")).strip()
    if not (question and answer and statement):
        return None

    distractors = tuple(
        str(d).strip() for d in raw.get("distractors", []) if str(d).strip()
    )
    number = raw.get("number")
    return CorpusFact(
        sport=sport,
        question=question,
        answer=answer,
        distractors=distractors,
        statement=statement,
        explanation=str(raw.get("explanation", "")).strip(),
        number=float(number) if isinstance(number, (int, float)) else None,
        unit=str(raw.get("unit", "")).strip(),
        tags=tuple(str(t).strip() for t in raw.get("tags", []) if str(t).strip()),
    )


def _load_file(path: Path) -> tuple[Sport | None, list[CorpusFact], list[CorpusDebate]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Skipping corpus file %s: %s", path.name, exc)
        return None, [], []

    sport = _parse_sport(payload.get("sport", ""))
    if sport is None:
        logger.warning(
            "Skipping corpus file %s: unknown sport %r", path.name, payload.get("sport")
        )
        return None, [], []

    facts = [f for f in (_parse_fact(sport, r) for r in payload.get("facts", [])) if f]
    debates = [
        CorpusDebate(
            sport=sport,
            prompt=str(d.get("prompt", "")).strip(),
            left=str(d.get("left", "")).strip(),
            right=str(d.get("right", "")).strip(),
        )
        for d in payload.get("debates", [])
        if str(d.get("prompt", "")).strip()
        and str(d.get("left", "")).strip()
        and str(d.get("right", "")).strip()
    ]
    return sport, facts, debates


@lru_cache(maxsize=4)
def load_corpus(directory: str | None = None) -> Corpus:
    """Load and cache every seed file. A missing directory is not an error."""
    base = Path(directory) if directory else CORPUS_DIR
    corpus = Corpus()
    if not base.is_dir():
        logger.info("No corpus directory at %s", base)
        return corpus

    files: list[str] = []
    for path in sorted(base.glob("*.json")):
        sport, facts, debates = _load_file(path)
        if sport is None:
            continue
        files.append(path.name)
        if facts:
            corpus.facts[sport] = corpus.facts.get(sport, ()) + tuple(facts)
        if debates:
            corpus.debates[sport] = corpus.debates.get(sport, ()) + tuple(debates)

    corpus.source_files = tuple(files)
    logger.info(
        "Corpus loaded: %d facts, %d debates across %d sports",
        corpus.total_facts,
        corpus.total_debates,
        len(corpus.facts),
    )
    return corpus
