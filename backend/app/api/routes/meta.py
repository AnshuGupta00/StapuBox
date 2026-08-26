"""GET /api/meta — the option lists and per-type contracts the dashboard needs.

Serving these from the backend keeps the UI's dropdowns and the generator
registry from drifting apart: add a sport or a content type once, and the
dashboard picks it up.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.generators import GENERATORS
from app.schemas.common import (
    FACTUAL_TYPES,
    ContentType,
    Difficulty,
    Sport,
)
from app.services.engagement_service import SURFACE_MAP

router = APIRouter(tags=["meta"])

#: One-line summary of each format's answer contract, mirroring the schemas.
_CONTRACTS: dict[ContentType, str] = {
    ContentType.MCQ: "4 options, exactly 1 correct",
    ContentType.TRUE_FALSE: "declarative statement, boolean verdict",
    ContentType.POLL: "2 options, no correct answer (opinion-based)",
    ContentType.FILL_BLANK: "one blank, 4 candidate fills",
    ContentType.GUESS_NUMBER: "numeric target with an accepted ± range",
}

_LABELS: dict[ContentType, str] = {
    ContentType.MCQ: "Multiple Choice",
    ContentType.TRUE_FALSE: "True / False",
    ContentType.POLL: "This or That",
    ContentType.FILL_BLANK: "Fill in the Blank",
    ContentType.GUESS_NUMBER: "Guess the Number",
}


@router.get("/meta")
def meta() -> dict[str, object]:
    return {
        "sports": [s.value for s in Sport],
        "difficulties": [d.value for d in Difficulty],
        "content_types": [
            {
                "value": ct.value,
                "label": _LABELS.get(ct, ct.value),
                "contract": _CONTRACTS.get(ct, ""),
                "fact_checked": ct in FACTUAL_TYPES,
                "sticker": SURFACE_MAP[ct][0],
                "surface": SURFACE_MAP[ct][1].value,
            }
            for ct in GENERATORS
        ],
    }
