"""Google Gemini integration.

Two distinct call shapes:

* research() uses Gemini with Google Search grounding to gather fresh,
  citable sports facts.
* generate_batch() uses Gemini structured JSON output so generated drafts
  conform to the requested Pydantic schema.

When no Gemini API key is configured, the service falls back to mock mode.
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


RESEARCH_SYSTEM = """\
You are a sports research assistant preparing evidence for a fact-checked quiz.

Search the web, then report only what you verified. For each finding write one
compact line:

FACT: <the claim, including every exact figure, name, date and opponent>

Rules:
- Prefer settled, checkable facts: final scores, career totals, titles won,
  records held, tournament winners.
- Include the exact numbers.
- Note the date or season a figure is current as of.
- If a claim is disputed between sources, omit it entirely.
- No preamble and no summary.
- Output only FACT: lines.
"""


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
    """Thin wrapper around the Google Gemini API."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client: Any | None = None
        self.call_count = 0

    # ------------------------------------------------------------------
    # Client
    # ------------------------------------------------------------------

    @property
    def is_live(self) -> bool:
        return self.settings.live_llm

    @property
    def client(self) -> Any:
        """Lazily construct the Gemini client."""
        if self._client is None:
            try:
                from google import genai
            except ImportError as exc:
                raise LLMError(
                    "The 'google-genai' package is not installed. "
                    "Add `google-genai` to requirements.txt."
                ) from exc

            if not self.settings.gemini_api_key:
                raise LLMError(
                    "GEMINI_API_KEY is not configured."
                )

            self._client = genai.Client(
                api_key=self.settings.gemini_api_key
            )

        return self._client

    # ------------------------------------------------------------------
    # Research / Google Search
    # ------------------------------------------------------------------

    def research(
        self,
        *,
        sport: Sport,
        topic: str = "",
        difficulty: Difficulty | None = None,
        max_uses: int | None = None,
    ) -> ResearchResult:
        """Gather fresh facts using Gemini Google Search grounding."""

        if not self.is_live:
            notes, sources = mock_llm.mock_research(
                sport=sport,
                topic=topic,
            )

            return ResearchResult(
                notes=notes,
                sources=sources,
                used_web_search=False,
                degraded=False,
                messages=[
                    "Mock mode: offline sample facts only, "
                    "no Google Search performed."
                ],
            )

        query = self._build_research_query(
            sport,
            topic,
            difficulty,
        )

        prompt = f"""
{RESEARCH_SYSTEM}

{query}

Search the web and return 10-15 verified FACT: lines.
"""

        try:
            response = self.client.interactions.create(
                model=self.settings.llm_model,
                input=prompt,
                tools=[
                    {
                        "type": "google_search"
                    }
                ],
            )
        except Exception as exc:
            logger.warning(
                "Gemini web research failed: %s",
                exc,
            )

            return ResearchResult(
                degraded=True,
                messages=[
                    f"Web search unavailable: {type(exc).__name__}"
                ],
            )

        self.call_count += 1

        notes = getattr(
            response,
            "output_text",
            "",
        ) or ""

        sources = self._harvest_gemini_sources(response)

        return ResearchResult(
            notes=notes.strip(),
            sources=sources,
            used_web_search=bool(sources),
            degraded=False,
            messages=(
                []
                if sources
                else ["Google Search returned no usable citations."]
            ),
        )

    # ------------------------------------------------------------------
    # Research query
    # ------------------------------------------------------------------

    def _build_research_query(
        self,
        sport: Sport,
        topic: str,
        difficulty: Difficulty | None,
    ) -> str:

        parts = [
            f"Research verifiable {sport.value} facts suitable "
            "for quiz questions."
        ]

        if topic.strip():
            parts.append(
                f"Focus on: {topic.strip()}."
            )
        else:
            parts.append(
                "Cover a mix of recent results from the current "
                "season and established all-time records."
            )

        if difficulty is Difficulty.HARD:
            parts.append(
                "Prioritise precise statistics and "
                "less-celebrated records."
            )

        elif difficulty is Difficulty.EASY:
            parts.append(
                "Prioritise headline achievements that "
                "casual fans know."
            )

        parts.append(
            "Report 10-15 FACT: lines."
        )

        return " ".join(parts)

    # ------------------------------------------------------------------
    # Harvest Google citations
    # ------------------------------------------------------------------

    def _harvest_gemini_sources(
        self,
        response: Any,
    ) -> list[Source]:

        sources: list[Source] = []
        seen_urls: set[str] = set()

        steps = getattr(
            response,
            "steps",
            [],
        ) or []

        counter = 0

        for step in steps:

            if getattr(step, "type", None) != "model_output":
                continue

            content_blocks = getattr(
                step,
                "content",
                [],
            ) or []

            for block in content_blocks:

                if getattr(block, "type", None) != "text":
                    continue

                annotations = getattr(
                    block,
                    "annotations",
                    [],
                ) or []

                for annotation in annotations:

                    if getattr(
                        annotation,
                        "type",
                        None,
                    ) != "url_citation":
                        continue

                    url = getattr(
                        annotation,
                        "url",
                        None,
                    )

                    if not url or url in seen_urls:
                        continue

                    seen_urls.add(url)

                    counter += 1

                    title = (
                        getattr(
                            annotation,
                            "title",
                            "",
                        )
                        or url
                    ).strip()

                    sources.append(
                        Source(
                            ref=f"W{counter}",
                            kind=SourceKind.WEB_SEARCH,
                            title=title,
                            url=url,
                            snippet="Google Search grounded source",
                        )
                    )

        return sources

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def generate_batch(
        self,
        *,
        draft_cls: type[TDraft],
        system: str,
        user: str,
        count: int,
    ) -> list[TDraft]:
        """Generate drafts using Gemini structured JSON output."""

        if not self.is_live:
            return mock_llm.mock_drafts(
                draft_cls=draft_cls,
                count=count,
                user_prompt=user,
            )

        batch_cls = _batch_model(draft_cls)

        prompt = f"""
{system}

{user}

Generate exactly {count} items.

Return ONLY valid JSON matching the supplied schema.
"""

        try:
            response = self.client.interactions.create(
                model=self.settings.llm_model,
                input=prompt,
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": batch_cls.model_json_schema(),
                },
            )

        except Exception as exc:
            raise LLMError(
                f"Gemini generation failed: {exc}"
            ) from exc

        self.call_count += 1

        raw = getattr(
            response,
            "output_text",
            "",
        ) or ""

        if not raw.strip():
            raise LLMError(
                "Gemini returned empty output."
            )

        try:
            parsed = batch_cls.model_validate_json(
                raw
            )
        except Exception as exc:
            raise LLMError(
                f"Could not parse Gemini structured output: {exc}"
            ) from exc

        return list(
            getattr(parsed, "items", [])
            or []
        )


# ----------------------------------------------------------------------
# Batch schema
# ----------------------------------------------------------------------

def _batch_model(
    draft_cls: type[BaseModel],
) -> type[BaseModel]:
    """Wrap a draft model in {'items': [...]}."""

    return create_model(
        f"{draft_cls.__name__}Batch",
        items=(
            list[draft_cls],
            ...,
        ),
    )


# ----------------------------------------------------------------------
# Singleton
# ----------------------------------------------------------------------

_service: LLMService | None = None


def get_llm_service() -> LLMService:
    """Process-wide Gemini service singleton."""

    global _service

    if _service is None:
        _service = LLMService()

    return _service