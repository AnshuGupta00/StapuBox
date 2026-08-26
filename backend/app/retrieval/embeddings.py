"""Embedding function selection for ChromaDB.

Defaults to ChromaDB's bundled ONNX ``all-MiniLM-L6-v2``, which is the same
model ``sentence-transformers`` would download but without the PyTorch
dependency. Set ``EMBEDDING_BACKEND=sentence-transformers`` to opt into the
heavier path.
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


def get_embedding_function(settings: Settings | None = None) -> Any:
    """Return a Chroma-compatible embedding function.

    Returning ``None`` lets Chroma apply its own default, which is the desired
    behaviour for the ``default`` backend and the safest fallback if an optional
    dependency is missing.
    """
    settings = settings or get_settings()
    backend = settings.embedding_backend.strip().lower()

    if backend in {"", "default", "onnx", "chroma"}:
        try:
            from chromadb.utils import embedding_functions

            return embedding_functions.ONNXMiniLM_L6_V2()
        except Exception as exc:  # noqa: BLE001 - fall back to Chroma's default
            logger.info("Using Chroma's built-in default embeddings (%s)", exc)
            return None

    if backend in {"sentence-transformers", "sentence_transformers", "st"}:
        try:
            from chromadb.utils import embedding_functions

            return embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "sentence-transformers backend unavailable (%s); "
                "falling back to the default ONNX embeddings.",
                exc,
            )
            return None

    logger.warning("Unknown EMBEDDING_BACKEND=%r; using Chroma default.", backend)
    return None


def embedding_backend_name(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    backend = settings.embedding_backend.strip().lower()
    if backend in {"sentence-transformers", "sentence_transformers", "st"}:
        return "sentence-transformers/all-MiniLM-L6-v2"
    return "chromadb ONNX all-MiniLM-L6-v2"
