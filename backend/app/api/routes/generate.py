"""POST /api/generate — batch generation, optionally mixing content types."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.agent.orchestrator import ContentAgent, get_agent
from app.schemas.request import GenerateRequest
from app.schemas.response import GenerateResponse
from app.services.llm_service import LLMError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["generation"])


@router.post("/generate", response_model=GenerateResponse)
def generate(
    request: GenerateRequest,
    agent: ContentAgent = Depends(get_agent),
) -> GenerateResponse:
    """Generate a batch of engagement content.

    Defined with ``def`` rather than ``async def`` on purpose: generation makes
    blocking HTTP calls, so FastAPI runs it in a worker thread instead of
    stalling the event loop.

    A short batch is returned with HTTP 200 and an explanation in
    ``diagnostics.warnings`` — items dropped for being ungrounded or duplicated
    are a feature, not a server error.
    """
    try:
        return agent.generate(request)
    except LLMError as exc:
        logger.warning("Generation failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - surface as 500 with a clean message
        logger.exception("Unexpected generation error")
        raise HTTPException(
            status_code=500, detail=f"{type(exc).__name__}: {exc}"
        ) from exc
