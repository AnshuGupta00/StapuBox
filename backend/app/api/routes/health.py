"""GET /api/health — is the agent actually wired up?

Reports every dependency's real state (LLM mode, vector DB count, freshness
ledger) so a setup problem is visible before the first generation attempt rather
than as a mystery empty batch.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.agent.freshness import get_ledger
from app.config import get_settings
from app.retrieval.chroma_client import get_knowledge_base
from app.retrieval.embeddings import embedding_backend_name

router = APIRouter(tags=["meta"])


@router.get("/health")
def health() -> dict[str, object]:
    settings = get_settings()
    kb = get_knowledge_base()

    kb_count = kb.count()
    checks = {
        "llm": {
            "mode": "live" if settings.live_llm else "mock",
            "model": settings.llm_model,
            "api_key_configured": bool(settings.anthropic_api_key),
        },
        "web_search": {
            "enabled": settings.enable_web_search and settings.live_llm,
            "tool": "server-side (Anthropic web_search)",
            "max_uses": settings.web_search_max_uses,
            "note": (
                None
                if settings.live_llm
                else "Mock mode: offline sample facts are used instead of live search."
            ),
        },
        "knowledge_base": {
            "available": kb.available,
            "collection": settings.chroma_collection,
            "documents": kb_count,
            "embeddings": embedding_backend_name(),
            "path": str(settings.chroma_persist_dir),
            "reason": kb.unavailable_reason or None,
            "hint": (
                "Run `python scripts/ingest_data.py` to seed the knowledge base."
                if kb.available and kb_count == 0
                else None
            ),
        },
        "freshness": get_ledger().stats(),
    }

    # "degraded" rather than "unhealthy": the app is designed to keep working
    # with a missing backend, just with less grounding.
    degraded = not kb.available or kb_count == 0
    return {
        "status": "degraded" if degraded else "ok",
        "mock_mode": not settings.live_llm,
        "checks": checks,
    }
