"""ChromaDB access for stable and historical sports facts.

The vector store holds the slow-moving half of the knowledge base — all-time
records, tournament winners, rules — while web search covers anything that
changes week to week. Failures here are non-fatal by design: the agent degrades
to web-only retrieval and says so in the response.
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import Settings, get_settings
from app.retrieval.embeddings import get_embedding_function
from app.schemas.common import Source, SourceKind, Sport

logger = logging.getLogger(__name__)


class KnowledgeBase:
    """Lazy wrapper around a persistent Chroma collection."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._collection: Any | None = None
        self._unavailable_reason: str | None = None

    # ----------------------------------------------------------------- lifecycle

    @property
    def available(self) -> bool:
        return self._get_collection() is not None

    @property
    def unavailable_reason(self) -> str | None:
        return self._unavailable_reason

    def _get_collection(self) -> Any | None:
        if self._collection is not None:
            return self._collection
        if self._unavailable_reason is not None:
            return None

        try:
            import chromadb

            self.settings.chroma_persist_dir.mkdir(parents=True, exist_ok=True)
            client = chromadb.PersistentClient(
                path=str(self.settings.chroma_persist_dir)
            )
            kwargs: dict[str, Any] = {
                "name": self.settings.chroma_collection,
                "metadata": {"hnsw:space": "cosine"},
            }
            embedder = get_embedding_function(self.settings)
            if embedder is not None:
                kwargs["embedding_function"] = embedder

            self._collection = client.get_or_create_collection(**kwargs)
            return self._collection
        except ImportError as exc:
            self._unavailable_reason = (
                "chromadb is not installed; run `pip install -r backend/requirements.txt`"
            )
            logger.warning("ChromaDB unavailable: %s", exc)
        except Exception as exc:  # noqa: BLE001 - degrade instead of failing a request
            self._unavailable_reason = f"ChromaDB error: {type(exc).__name__}: {exc}"
            logger.warning("ChromaDB unavailable: %s", exc)
        return None

    def count(self) -> int:
        collection = self._get_collection()
        if collection is None:
            return 0
        try:
            return int(collection.count())
        except Exception:  # noqa: BLE001
            return 0

    # -------------------------------------------------------------------- writes

    def upsert(self, documents: list[dict[str, Any]]) -> int:
        """Insert or update documents.

        Each dict needs ``id`` and ``text``; everything else is stored as
        metadata. Returns the number of documents written.
        """
        collection = self._get_collection()
        if collection is None:
            raise RuntimeError(self._unavailable_reason or "ChromaDB unavailable")
        if not documents:
            return 0

        ids = [str(d["id"]) for d in documents]
        texts = [str(d["text"]) for d in documents]
        metadatas = [
            {
                k: v
                for k, v in d.items()
                if k not in {"id", "text"} and isinstance(v, (str, int, float, bool))
            }
            or {"source": "seed"}
            for d in documents
        ]
        collection.upsert(ids=ids, documents=texts, metadatas=metadatas)
        return len(ids)

    # -------------------------------------------------------------------- reads

    def query(
        self,
        *,
        text: str,
        sport: Sport | None = None,
        n_results: int = 8,
        start_ref: int = 0,
    ) -> list[Source]:
        """Semantic search, optionally filtered to one sport.

        ``start_ref`` offsets the generated citation handles (``K1``, ``K2``, …)
        so they never collide with web-search handles in the same context pack.
        """
        collection = self._get_collection()
        if collection is None:
            return []

        where = {"sport": sport.value} if sport is not None else None
        try:
            result = collection.query(
                query_texts=[text],
                n_results=max(1, n_results),
                where=where,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Chroma query failed: %s", exc)
            return []

        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]

        sources: list[Source] = []
        for i, doc in enumerate(documents):
            meta = metadatas[i] if i < len(metadatas) else {}
            meta = meta or {}
            distance = distances[i] if i < len(distances) else None
            title = str(meta.get("title") or meta.get("topic") or "knowledge base entry")
            if distance is not None:
                title = f"{title} (similarity {max(0.0, 1.0 - float(distance)):.2f})"
            sources.append(
                Source(
                    ref=f"K{start_ref + i + 1}",
                    kind=SourceKind.VECTOR_DB,
                    title=title,
                    snippet=str(doc),
                )
            )
        return sources


_kb: KnowledgeBase | None = None


def get_knowledge_base() -> KnowledgeBase:
    """Process-wide singleton — Chroma clients are expensive to construct."""
    global _kb
    if _kb is None:
        _kb = KnowledgeBase()
    return _kb
