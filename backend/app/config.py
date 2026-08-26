"""Central configuration, loaded once from the environment.

Every tunable lives here so the rest of the app never reads ``os.environ``
directly. Paths are resolved relative to the backend package root so the
app behaves the same whether it is started from ``backend/`` or the repo root.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# backend/app/config.py -> backend/
BACKEND_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_ROOT.parent

load_dotenv(BACKEND_ROOT / ".env")


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "").strip())
    except (TypeError, ValueError):
        return default


def _path(name: str, default: str) -> Path:
    raw = os.getenv(name, "").strip() or default
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = (BACKEND_ROOT / candidate).resolve()
    return candidate


class Settings:
    """Immutable-by-convention settings snapshot."""

    def __init__(self) -> None:
        # LLM
        self.anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "").strip()
        self.llm_model: str = os.getenv("LLM_MODEL", "").strip() or "claude-opus-5"

        # Mock mode is implied when no key is configured, so a fresh clone
        # still runs end to end instead of failing on the first request.
        self.mock_llm: bool = _bool("MOCK_LLM", default=not self.anthropic_api_key)

        # Retrieval
        self.chroma_persist_dir: Path = _path("CHROMA_PERSIST_DIR", "../chroma_db")
        self.chroma_collection: str = (
            os.getenv("CHROMA_COLLECTION", "").strip() or "sports_knowledge"
        )
        self.embedding_backend: str = (
            os.getenv("EMBEDDING_BACKEND", "").strip() or "default"
        )
        self.enable_web_search: bool = _bool("ENABLE_WEB_SEARCH", default=True)
        self.web_search_max_uses: int = _int("WEB_SEARCH_MAX_USES", 6)

        # Freshness
        self.history_path: Path = _path(
            "HISTORY_PATH", "../data/generated_history/ledger.jsonl"
        )
        self.novelty_lookback: int = _int("NOVELTY_LOOKBACK", 400)

        # Server
        raw_origins = os.getenv("CORS_ORIGINS", "").strip()
        self.cors_origins: list[str] = (
            [o.strip() for o in raw_origins.split(",") if o.strip()]
            if raw_origins
            else ["http://localhost:5173", "http://127.0.0.1:5173"]
        )

    @property
    def live_llm(self) -> bool:
        """True when real Anthropic calls should be made."""
        return not self.mock_llm and bool(self.anthropic_api_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

# Backwards-compatible module-level alias used by the ingestion script.
CHROMA_PERSIST_DIR = str(settings.chroma_persist_dir)
