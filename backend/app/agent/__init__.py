"""The agent layer: retrieval routing, freshness tracking, orchestration."""

from __future__ import annotations

from app.agent.freshness import NoveltyLedger, get_ledger
from app.agent.orchestrator import ContentAgent, allocate, get_agent
from app.agent.router import (
    RetrievalPlan,
    context_for,
    plan_retrieval,
    retrieve,
    to_report,
)

__all__ = [
    "ContentAgent",
    "NoveltyLedger",
    "RetrievalPlan",
    "allocate",
    "context_for",
    "get_agent",
    "get_ledger",
    "plan_retrieval",
    "retrieve",
    "to_report",
]
