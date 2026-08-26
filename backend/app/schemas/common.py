"""Shared enums and value objects used across every content type."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Sport(str, Enum):
    CRICKET = "Cricket"
    FOOTBALL = "Football"
    TENNIS = "Tennis"
    BADMINTON = "Badminton"
    BASKETBALL = "Basketball"
    HOCKEY = "Hockey"
    ATHLETICS = "Athletics"
    FORMULA1 = "Formula 1"
    KABADDI = "Kabaddi"
    CHESS = "Chess"


class Difficulty(str, Enum):
    EASY = "Easy"
    MEDIUM = "Medium"
    HARD = "Hard"


class ContentType(str, Enum):
    MCQ = "MCQ"
    TRUE_FALSE = "TrueFalse"
    POLL = "Poll"
    FILL_BLANK = "FillBlank"
    GUESS_NUMBER = "GuessNumber"


#: Types whose factual claims must be grounded in retrieved context.
FACTUAL_TYPES: frozenset[ContentType] = frozenset(
    {
        ContentType.MCQ,
        ContentType.TRUE_FALSE,
        ContentType.FILL_BLANK,
        ContentType.GUESS_NUMBER,
    }
)

#: Types that are opinion-based by design and are never fact-checked.
OPINION_TYPES: frozenset[ContentType] = frozenset({ContentType.POLL})


class SourceKind(str, Enum):
    WEB_SEARCH = "web_search"
    VECTOR_DB = "vector_db"
    OPINION = "opinion"


class Source(BaseModel):
    """A single retrieved evidence item that an answer can cite.

    ``ref`` is the short handle (``W1``, ``K3``) the LLM uses inside prompts,
    which lets us map a generated citation back to real retrieved evidence
    instead of trusting the model to reproduce a URL correctly.
    """

    ref: str = Field(description="Short citation handle, e.g. 'W1' or 'K2'.")
    kind: SourceKind
    title: str = ""
    url: str | None = None
    snippet: str = ""

    def label(self) -> str:
        if self.kind is SourceKind.WEB_SEARCH:
            return f"Web search — {self.title or self.url or 'result'}"
        if self.kind is SourceKind.VECTOR_DB:
            return f"Knowledge base — {self.title or 'document'}"
        return "Opinion-based (not fact-checked)"


class InstagramSurface(str, Enum):
    """Where the item is meant to be published."""

    STORY = "Story"
    FEED = "Feed"
    REEL_CAPTION = "Reel Caption"


class InstagramPayload(BaseModel):
    """Text pre-shaped for Instagram's native sticker and caption tools.

    Instagram truncates sticker text, so each generated item carries a
    ready-to-paste payload plus the character budget it was checked against.
    """

    sticker: str = Field(
        description="Native tool to use, e.g. 'Quiz sticker' or 'Poll sticker'."
    )
    surface: InstagramSurface
    prompt_text: str = Field(description="Text for the question/prompt field.")
    option_texts: list[str] = Field(default_factory=list)
    caption: str = Field(default="", description="Suggested feed/reel caption.")
    hashtags: list[str] = Field(default_factory=list)
    within_limits: bool = Field(
        default=True,
        description="False when any field exceeded its recommended character budget.",
    )
    limit_warnings: list[str] = Field(default_factory=list)
