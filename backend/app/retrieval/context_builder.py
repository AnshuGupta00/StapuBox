"""Assemble retrieved evidence into a single citable context pack.

The pack is the only factual input the generation prompt receives. Each piece of
evidence gets a short handle (``W1`` for web search, ``K1`` for the vector DB)
that the model must cite. Because we own the handle table, a citation can be
resolved back to real evidence — a model that invents ``W9`` produces an
unresolvable citation, which the validation layer treats as ungrounded.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.retrieval.chroma_client import KnowledgeBase, get_knowledge_base
from app.retrieval.web_search import search_sport_facts
from app.schemas.common import Difficulty, Source, SourceKind, Sport
from app.services.llm_service import LLMService


@dataclass
class ContextPack:
    """Retrieved evidence plus the metadata needed to report on it."""

    text: str = ""
    sources: list[Source] = field(default_factory=list)
    web_used: bool = False
    web_results: int = 0
    vector_hits: int = 0
    degraded: bool = False
    messages: list[str] = field(default_factory=list)
    research_notes: str = ""

    def by_ref(self) -> dict[str, Source]:
        return {s.ref: s for s in self.sources}

    def resolve(self, refs: list[str]) -> list[Source]:
        """Map claimed citation handles to real sources, dropping inventions."""
        table = self.by_ref()
        seen: set[str] = set()
        resolved: list[Source] = []
        for raw in refs:
            ref = raw.strip().upper()
            if ref in table and ref not in seen:
                seen.add(ref)
                resolved.append(table[ref])
        return resolved

    @property
    def is_empty(self) -> bool:
        return not self.sources and not self.text.strip()


def build_context(
    *,
    sport: Sport,
    difficulty: Difficulty | None = None,
    topic: str = "",
    use_web_search: bool = True,
    kb_results: int = 8,
    knowledge_base: KnowledgeBase | None = None,
    llm: LLMService | None = None,
) -> ContextPack:
    """Retrieve from web search and the vector DB, then merge into one pack."""
    pack = ContextPack()
    sections: list[str] = []

    # --- Fresh / fast-changing facts -------------------------------------
    if use_web_search:
        evidence = search_sport_facts(
            sport=sport, topic=topic, difficulty=difficulty, llm=llm
        )
        pack.web_used = evidence.used
        pack.degraded = pack.degraded or evidence.degraded
        pack.messages.extend(evidence.messages)
        pack.research_notes = evidence.notes

        # Renumber web handles so they are contiguous from W1. Evidence that is
        # not from live search (the offline sample bank) keeps its own handle,
        # so its citations still resolve.
        web_index = 0
        for source in evidence.sources:
            if source.kind is SourceKind.WEB_SEARCH:
                web_index += 1
                pack.sources.append(source.model_copy(update={"ref": f"W{web_index}"}))
            else:
                pack.sources.append(source)
        pack.web_results = web_index

        if evidence.notes.strip():
            header = (
                "--- WEB RESEARCH (fresh facts, verified by search) ---"
                if evidence.used
                else "--- RESEARCH NOTES (offline sample facts) ---"
            )
            sections.append(header + "\n" + evidence.notes.strip())
        if pack.sources:
            listing = "\n".join(
                f"[{s.ref}] {s.title}" + (f" — {s.url}" if s.url else "")
                for s in pack.sources
            )
            label = "WEB SOURCES" if web_index else "SAMPLE SOURCES (offline mode)"
            sections.append(f"--- {label} ---\n" + listing)

    # --- Stable / historical facts ---------------------------------------
    kb = knowledge_base or get_knowledge_base()
    kb_query = f"{sport.value} {topic}".strip() or sport.value
    kb_sources = kb.query(
        text=kb_query, sport=sport, n_results=kb_results, start_ref=0
    )
    if kb_sources:
        pack.sources.extend(kb_sources)
        pack.vector_hits = len(kb_sources)
        listing = "\n".join(f"[{s.ref}] {s.snippet}" for s in kb_sources)
        sections.append(
            "--- KNOWLEDGE BASE (stable historical facts) ---\n" + listing
        )
    elif not kb.available:
        pack.degraded = True
        reason = kb.unavailable_reason or "vector DB unavailable"
        pack.messages.append(f"Knowledge base not queried: {reason}")
    else:
        pack.messages.append(
            f"Knowledge base has no entries for {sport.value}. "
            "Run `python scripts/ingest_data.py` to seed it."
        )

    pack.text = "\n\n".join(sections)

    if pack.is_empty:
        pack.degraded = True
        pack.messages.append(
            "No evidence retrieved — factual generation will be blocked."
        )

    return pack


def opinion_context(pack: ContextPack) -> ContextPack:
    """A pack trimmed for poll generation.

    Polls need topical hooks, not citable evidence, so the source table is
    replaced with a single opinion marker. This keeps a poll from ever
    presenting a resolvable factual citation.
    """
    trimmed = ContextPack(
        text=pack.text,
        sources=[
            Source(
                ref="OPINION",
                kind=SourceKind.OPINION,
                title="Opinion-based content",
                snippet="This-or-That polls are not fact-checked by design.",
            )
        ],
        web_used=pack.web_used,
        web_results=pack.web_results,
        vector_hits=pack.vector_hits,
        degraded=pack.degraded,
        messages=list(pack.messages),
        research_notes=pack.research_notes,
    )
    return trimmed
