"""FastAPI application entry point.

Run from the ``backend`` directory:

    uvicorn app.main:app --reload
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.generate import router as generate_router
from app.api.routes.health import router as health_router
from app.api.routes.meta import router as meta_router
from app.api.routes.regenerate import router as regenerate_router
from app.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
logger = logging.getLogger("app")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Make the LLM mode obvious in the logs before the first request."""
    if settings.live_llm:
        logger.info("LLM: live (%s)", settings.llm_model)
    else:
        logger.warning(
            "LLM: MOCK mode — deterministic offline content. Set ANTHROPIC_API_KEY "
            "in backend/.env for live generation with web search."
        )
    yield


app = FastAPI(
    title="AI Sports Engagement Content Agent",
    version="1.0.0",
    lifespan=lifespan,
    description=(
        "Generates grounded, Instagram-ready sports engagement content in five "
        "formats: MCQ, True/False, This-or-That poll, fill-in-the-blank and "
        "guess-the-number. Facts are grounded in server-side web search plus a "
        "ChromaDB knowledge base, and every factual claim carries the citation "
        "handles that support it."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api")
app.include_router(meta_router, prefix="/api")
app.include_router(generate_router, prefix="/api")
app.include_router(regenerate_router, prefix="/api")


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {
        "name": "AI Sports Engagement Content Agent",
        "docs": "/docs",
        "health": "/api/health",
    }
