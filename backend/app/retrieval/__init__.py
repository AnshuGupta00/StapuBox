"""Retrieval: ChromaDB for stable facts, server-side web search for fresh ones."""

from __future__ import annotations

from app.retrieval.chroma_client import KnowledgeBase, get_knowledge_base
from app.retrieval.context_builder import ContextPack, build_context, opinion_context
from app.retrieval.embeddings import embedding_backend_name, get_embedding_function
from app.retrieval.web_search import WebEvidence, search_sport_facts

__all__ = [
    "ContextPack",
    "KnowledgeBase",
    "WebEvidence",
    "build_context",
    "embedding_backend_name",
    "get_embedding_function",
    "get_knowledge_base",
    "opinion_context",
    "search_sport_facts",
]
