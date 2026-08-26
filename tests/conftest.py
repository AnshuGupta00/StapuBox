"""Shared test configuration.

Every test runs fully offline: mock LLM, a throwaway novelty ledger and a
throwaway Chroma directory. The environment is set *before* ``app.config`` is
imported, because settings are read once and cached.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

_TMP = Path(tempfile.mkdtemp(prefix="sports-agent-tests-"))

os.environ["MOCK_LLM"] = "1"
os.environ["HISTORY_PATH"] = str(_TMP / "ledger.jsonl")
os.environ["CHROMA_PERSIST_DIR"] = str(_TMP / "chroma")
os.environ["CHROMA_COLLECTION"] = "test_knowledge"

from app.agent.freshness import NoveltyLedger  # noqa: E402
from app.agent.orchestrator import ContentAgent  # noqa: E402
from app.retrieval.context_builder import ContextPack  # noqa: E402
from app.schemas.common import Source, SourceKind  # noqa: E402
from app.services.llm_service import get_llm_service  # noqa: E402


def pytest_sessionfinish(session, exitstatus) -> None:  # noqa: ARG001
    shutil.rmtree(_TMP, ignore_errors=True)


@pytest.fixture
def tmp_ledger(tmp_path: Path) -> NoveltyLedger:
    """An isolated novelty ledger, so one test's history cannot leak into another."""
    return NoveltyLedger(path=tmp_path / "ledger.jsonl")


@pytest.fixture
def agent(tmp_ledger: NoveltyLedger) -> ContentAgent:
    return ContentAgent(llm=get_llm_service(), ledger=tmp_ledger)


@pytest.fixture
def grounded_pack() -> ContextPack:
    """A minimal context pack whose handles resolve, for unit-testing generators."""
    return ContextPack(
        text="[T1] Test evidence.",
        sources=[
            Source(
                ref="T1",
                kind=SourceKind.VECTOR_DB,
                title="Test source",
                snippet="Test evidence.",
            )
        ],
        vector_hits=1,
    )


@pytest.fixture
def client(agent: ContentAgent):
    """A test client whose agent keeps a per-test novelty ledger.

    Overriding the dependency (rather than using the process-wide agent) stops
    one test's generated history from shrinking the pool available to the next.
    """
    from fastapi.testclient import TestClient

    from app.agent.orchestrator import get_agent
    from app.main import app

    app.dependency_overrides[get_agent] = lambda: agent
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
