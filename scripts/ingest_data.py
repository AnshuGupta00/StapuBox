"""Seed the ChromaDB knowledge base from the hand-checked corpus in ``data/raw``.

Run once after installing dependencies (and again whenever you add facts):

    python scripts/ingest_data.py

The first run downloads ChromaDB's bundled ONNX embedding model
(all-MiniLM-L6-v2, ~80 MB) into ``~/.cache/chroma``. Ingestion is idempotent:
each document id is derived from its statement, so re-running updates entries
instead of duplicating them.

Options
-------
``--dry-run``   Show what would be written without touching ChromaDB.
``--sport``     Ingest one sport only (repeatable), e.g. ``--sport Cricket``.
``--stats``     Print collection counts and exit.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# The app package lives in backend/, one level below the repo root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.corpus import CORPUS_DIR, Corpus, load_corpus  # noqa: E402
from app.retrieval.chroma_client import get_knowledge_base  # noqa: E402
from app.schemas.common import Sport  # noqa: E402


def to_documents(corpus: Corpus, sports: list[Sport] | None = None) -> list[dict]:
    """Flatten the corpus into ChromaDB upsert payloads.

    The embedded text is ``statement + explanation`` — the declarative form —
    because queries at generation time are topical ("Cricket World Cup records"),
    not interrogative. The question and answer ride along as metadata so a
    retrieved hit can be shown to the user verbatim.
    """
    documents: list[dict] = []
    for fact in corpus.all_facts():
        if sports and fact.sport not in sports:
            continue
        documents.append(
            {
                "id": fact.doc_id(),
                "text": fact.document(),
                "title": fact.statement,
                **fact.metadata(),
            }
        )
    return documents


def parse_sports(values: list[str]) -> list[Sport]:
    known = {s.value.casefold(): s for s in Sport}
    resolved: list[Sport] = []
    for value in values:
        sport = known.get(value.strip().casefold())
        if sport is None:
            raise SystemExit(
                f"Unknown sport {value!r}. Options: {', '.join(s.value for s in Sport)}"
            )
        resolved.append(sport)
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="don't write to ChromaDB")
    parser.add_argument(
        "--sport", action="append", default=[], help="limit to one sport (repeatable)"
    )
    parser.add_argument("--stats", action="store_true", help="show counts and exit")
    args = parser.parse_args()

    kb = get_knowledge_base()

    if args.stats:
        print(f"collection : {kb.settings.chroma_collection}")
        print(f"path       : {kb.settings.chroma_persist_dir}")
        print(f"available  : {kb.available}{'' if kb.available else f' ({kb.unavailable_reason})'}")
        print(f"documents  : {kb.count()}")
        return 0

    corpus = load_corpus()
    if corpus.is_empty:
        print(f"No corpus files found in {CORPUS_DIR}. Nothing to ingest.")
        return 1

    sports = parse_sports(args.sport) if args.sport else None
    documents = to_documents(corpus, sports)

    print(f"corpus     : {corpus.total_facts} facts from {len(corpus.source_files)} files")
    print(f"selected   : {len(documents)} documents")
    for sport, facts in sorted(corpus.facts.items(), key=lambda kv: kv[0].value):
        if sports and sport not in sports:
            continue
        print(f"  {sport.value:12} {len(facts):3} facts")

    if args.dry_run:
        print("\n--dry-run: nothing written. Sample document:")
        if documents:
            sample = documents[0]
            print(f"  id   : {sample['id']}")
            print(f"  text : {sample['text'][:120]}")
            print(f"  meta : { {k: v for k, v in sample.items() if k not in {'id', 'text'}} }")
        return 0

    try:
        written = kb.upsert(documents)
    except RuntimeError as exc:
        print(f"\nIngestion failed: {exc}", file=sys.stderr)
        print(
            "Install dependencies with `pip install -r backend/requirements.txt` "
            "and check CHROMA_PERSIST_DIR is writable.",
            file=sys.stderr,
        )
        return 1

    print(f"\nUpserted {written} documents into '{kb.settings.chroma_collection}'.")
    print(f"Collection now holds {kb.count()} documents at {kb.settings.chroma_persist_dir}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
