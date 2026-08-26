"""Anthropic integration.

Two distinct call shapes, deliberately kept apart:

* :meth:`LLMService.research` runs Claude with the **server-side web search
  tool** to gather fresh evidence. Search executes on Anthropic's
  infrastructure, so no third-party search API key is required.
* :meth:`LLMService.generate_batch` runs Claude with **structured output**
  (``output_format``) and no tools, so the response is guaranteed to parse into
  the requesting content type's draft schema.

Splitting them means a flaky search never corrupts the generation contract, and
generation always sees evidence as plain text it must cite.

When no API key is configured the service transparently falls back to a
deterministic mock so the dashboard, schema validation, retrieval and dedup all
remain exercisable offline.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, TypeVar

from pydantic import BaseModel, create_model

from app.config import Settings, get_settings
from app.schemas.common import Difficulty, Source, SourceKind, Sport
from app.services import mock_llm

logger = logging.getLogger(__name__)

TDraft = TypeVar("TDraft", bound=BaseModel)

#: Server-side web search tool. The ``_20260209`` version adds dynamic
#: filtering (results are filtered before entering the context window).
WEB_SEARCH_TOOL_TYPE = "web_search_20260209"

RESEARCH_SYSTEM = """\
You are a sports research assistant preparing evidence for a fact-checked quiz.

Search the web, then report only what you verified. For each finding write one
compact line:

FACT: <the claim, including every exact figure, name, date and opponent>

Rules:
- Prefer settled, checkable facts: final scores, career totals, titles won,
  records held, tournament winners.
- Include the exact numbers. "Scored a lot" is useless; "scored 765 runs" is not.
- Note the date or season a figure is current as of, since totals change.
- If a claim is disputed between sources, omit it entirely.
- No preamble and no summary. Output only FACT: lines."""


@dataclass
class ResearchResult:
    notes: str = ""
    sources: list[Source] = field(default_factory=list)
    used_web_search: bool = False
    degraded: bool = False
    messages: list[str] = field(default_factory=list)


class LLMError(RuntimeError):
    """Raised when the model could not produce usable output."""


class LLMService:
    """Thin, testable wrapper around the Anthropic Messages API."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client: Any | None = None
        self.call_count = 0

    # ------------------------------------------------------------------ client

    @property
    def is_live(self) -> bool:
        return self.settings.live_llm

    @property
    def client(self) -> Any:
        """Lazily construct the SDK client so mock mode needs no dependency."""
        if self._client is None:
            try:
                import anthropic
            except ImportError as exc:  # pragma: no cover - env dependent
                raise LLMError(
                    "The 'anthropic' package is not installed. Run "
                    "`pip install -r backend/requirements.txt`, or set MOCK_LLM=1 "
                    "to run without an LLM."
                ) from exc
            self._client = anthropic.Anthropic(api_key=self.settings.anthropic_api_key)
        return self._client

    # ----------------------------------------------------------------- research

    def research(
        self,
        *,
        sport: Sport,
        topic: str = "",
        difficulty: Difficulty | None = None,
        max_uses: int | None = None,
    ) -> ResearchResult:
        """Gather fresh, citable facts using server-side web search."""
        if not self.is_live:
            notes, sources = mock_llm.mock_research(sport=sport, topic=topic)
            return ResearchResult(
                notes=notes,
                sources=sources,
                used_web_search=False,
                messages=[
                    "Mock mode: offline sample facts only, no web search performed."
                ],
            )

        query = self._build_research_query(sport, topic, difficulty)
        tool = {
            "type": WEB_SEARCH_TOOL_TYPE,
            "name": "web_search",
            "max_uses": max_uses or self.settings.web_search_max_uses,
        }

        messages: list[dict[str, Any]] = [{"role": "user", "content": query}]
        sources: list[Source] = []
        note_chunks: list[str] = []
        searched = False

        # A server-tool turn can stop with `pause_turn`; resume by replaying the
        # partial assistant turn until the model finishes.
        for _ in range(4):
            try:
                response = self.client.messages.create(
                    model=self.settings.llm_model,
                    max_tokens=8000,
                    thinking={"type": "adaptive"},
                    system=RESEARCH_SYSTEM,
                    tools=[tool],
                    messages=messages,
                )
            except Exception as exc:  # noqa: BLE001 - surfaced as degraded, not fatal
                logger.warning("Web research failed: %s", exc)
                return ResearchResult(
                    degraded=True,
                    messages=[f"Web search unavailable: {type(exc).__name__}"],
                )

            self.call_count += 1
            found, texts = self._harvest(response, start_index=len(sources))
            sources.extend(found)
            note_chunks.extend(texts)
            searched = searched or bool(found)

            if getattr(response, "stop_reason", None) != "pause_turn":
                break
            messages.append({"role": "assistant", "content": response.content})
        else:
            logger.warning("Research still paused after retries; using partial results")

        return ResearchResult(
            notes="\n".join(c for c in note_chunks if c.strip()).strip(),
            sources=sources,
            used_web_search=searched,
            messages=[] if searched else ["Web search returned no usable results."],
        )

    def _build_research_query(
        self, sport: Sport, topic: str, difficulty: Difficulty | None
    ) -> str:
        parts = [
            f"Research verifiable {sport.value} facts suitable for quiz questions."
        ]
        if topic.strip():
            parts.append(f"Focus on: {topic.strip()}.")
        else:
            parts.append(
                "Cover a mix of recent results from the current season and "
                "established all-time records."
            )
        if difficulty is Difficulty.HARD:
            parts.append(
                "Prioritise precise statistics and less-celebrated records."
            )
        elif difficulty is Difficulty.EASY:
            parts.append("Prioritise headline achievements that casual fans know.")
        parts.append("Report 10-15 FACT: lines.")
        return " ".join(parts)

    def _harvest(
        self, response: Any, *, start_index: int
    ) -> tuple[list[Source], list[str]]:
        """Pull web results and narrative text out of a response."""
        sources: list[Source] = []
        texts: list[str] = []
        counter = start_index

        for block in getattr(response, "content", []) or []:
            btype = getattr(block, "type", None)

            if btype == "text":
                texts.append(getattr(block, "text", "") or "")
                continue

            if btype != "web_search_tool_result":
                continue

            content = getattr(block, "content", None)
            # Server-tool errors return HTTP 200 with an error *object* here,
            # while success returns a *list* of results.
            if not isinstance(content, list):
                code = getattr(content, "error_code", None)
                if code:
                    logger.warning("web_search error: %s", code)
                continue

            for result in content:
                counter += 1
                sources.append(
                    Source(
                        ref=f"W{counter}",
                        kind=SourceKind.WEB_SEARCH,
                        title=(getattr(result, "title", "") or "").strip(),
                        url=getattr(result, "url", None),
                        snippet=self._clip(getattr(result, "page_age", "") or ""),
                    )
                )
        return sources, texts

    @staticmethod
    def _clip(text: str, limit: int = 300) -> str:
        text = " ".join(text.split())
        return text if len(text) <= limit else text[: limit - 1] + "…"

    # --------------------------------------------------------------- generation

    def generate_batch(
        self,
        *,
        draft_cls: type[TDraft],
        system: str,
        user: str,
        count: int,
    ) -> list[TDraft]:
        """Generate ``count`` drafts, guaranteed to satisfy ``draft_cls``.

        Uses structured output so the model cannot return prose or malformed
        JSON. Pydantic validation inside ``draft_cls`` runs as part of parsing,
        so anything returned here already meets the type's invariants.
        """
        if not self.is_live:
            return mock_llm.mock_drafts(draft_cls=draft_cls, count=count, user_prompt=user)

        batch_cls = _batch_model(draft_cls)

        try:
            response = self.client.messages.parse(
                model=self.settings.llm_model,
                max_tokens=16000,
                thinking={"type": "adaptive"},
                system=system,
                messages=[{"role": "user", "content": user}],
                output_format=batch_cls,
            )
        except Exception as exc:  # noqa: BLE001 - converted to a domain error
            raise LLMError(f"Generation call failed: {exc}") from exc

        self.call_count += 1

        if getattr(response, "stop_reason", None) == "refusal":
            details = getattr(response, "stop_details", None)
            category = getattr(details, "category", None) if details else None
            raise LLMError(f"Model declined the request (category={category}).")

        parsed = getattr(response, "parsed_output", None)
        if parsed is None:
            parsed = self._parse_fallback(response, batch_cls)

        return list(getattr(parsed, "items", []) or [])

    @staticmethod
    def _parse_fallback(response: Any, batch_cls: type[BaseModel]) -> BaseModel:
        """Recover the payload if ``parsed_output`` is unexpectedly empty."""
        import json

        for block in reversed(getattr(response, "content", []) or []):
            if getattr(block, "type", None) == "text":
                raw = getattr(block, "text", "") or ""
                if raw.strip():
                    try:
                        return batch_cls.model_validate(json.loads(raw))
                    except (json.JSONDecodeError, ValueError) as exc:
                        raise LLMError(f"Could not parse model output: {exc}") from exc
        raise LLMError("Model returned no text content.")


def _batch_model(draft_cls: type[BaseModel]) -> type[BaseModel]:
    """Wrap a draft model in ``{"items": [...]}`` for one-shot batch generation."""
    return create_model(
        f"{draft_cls.__name__}Batch",
        items=(list[draft_cls], ...),  # type: ignore[valid-type]
    )


_service: LLMService | None = None


def get_llm_service() -> LLMService:
    """Process-wide singleton, so the SDK client and call counter are shared."""
    global _service
    if _service is None:
        _service = LLMService()
    return _service
