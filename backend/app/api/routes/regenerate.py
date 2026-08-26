"""POST /api/regenerate — replace a single item in place."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.agent.orchestrator import ContentAgent, get_agent
from app.schemas.request import RegenerateRequest
from app.schemas.response import RegenerateResponse
from app.services.llm_service import LLMError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["generation"])


@router.post("/regenerate", response_model=RegenerateResponse)
def regenerate(
    request: RegenerateRequest,
    agent: ContentAgent = Depends(get_agent),
) -> RegenerateResponse:
    """Regenerate one item of a given type.

    Pass the text of the item being replaced (and anything else already on
    screen) in ``avoid`` so the agent is forced onto a different fact rather
    than rephrasing the same one.
    """
    try:
        response = agent.regenerate(request)
    except LLMError as exc:
        logger.warning("Regeneration failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected regeneration error")
        raise HTTPException(
            status_code=500, detail=f"{type(exc).__name__}: {exc}"
        ) from exc

    if response.item is None:
        # Every candidate was rejected. Report why instead of an empty 200 the
        # client would have to guess about.
        reason = "; ".join(response.diagnostics.warnings) or (
            "no valid, grounded, non-duplicate item could be produced"
        )
        raise HTTPException(status_code=422, detail=reason)

    return response
