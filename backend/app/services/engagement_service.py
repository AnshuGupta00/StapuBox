"""Turn a validated item into something a creator can actually post.

Two jobs:

1. :func:`build_instagram_payload` — shape the copy for Instagram's native
   tools (which sticker, which surface, pre-split option text) and flag anything
   that will be visually truncated.
2. :func:`score_engagement` — a transparent heuristic estimate of how much
   interaction an item should attract, so a creator can rank a batch instead of
   reading all of it.

The score is a documented heuristic, not a trained model: every contribution is
listed in :func:`score_breakdown` so the number is explainable rather than
magic.
"""

from __future__ import annotations

from app.schemas.base import BaseItem
from app.schemas.common import (
    ContentType,
    Difficulty,
    InstagramPayload,
    InstagramSurface,
    SourceKind,
    Sport,
)
from app.schemas.fill_blank import BLANK_TOKEN, FillBlankItem
from app.schemas.guess_number import GuessNumberItem
from app.schemas.mcq import MCQItem
from app.schemas.poll import PollItem
from app.schemas.true_false import TrueFalseItem
from app.utils.helpers import clip
from app.utils.validators import INSTAGRAM_LIMITS

#: Which native Instagram tool each type maps to, and the surface it suits best.
SURFACE_MAP: dict[ContentType, tuple[str, InstagramSurface]] = {
    # Quiz sticker natively supports up to 4 options with one marked correct.
    ContentType.MCQ: ("Quiz sticker", InstagramSurface.STORY),
    # Poll sticker with True/False as the two options.
    ContentType.TRUE_FALSE: ("Poll sticker", InstagramSurface.STORY),
    # The canonical this-or-that Story poll.
    ContentType.POLL: ("Poll sticker", InstagramSurface.STORY),
    # Reads naturally as a "complete the sentence" caption hook.
    ContentType.FILL_BLANK: ("Quiz sticker", InstagramSurface.REEL_CAPTION),
    # Free-text guesses belong in comments or the Questions sticker.
    ContentType.GUESS_NUMBER: ("Questions sticker", InstagramSurface.FEED),
}

_SPORT_TAGS: dict[Sport, tuple[str, ...]] = {
    Sport.CRICKET: ("cricket", "cricketquiz", "cricketlovers"),
    Sport.FOOTBALL: ("football", "footballquiz", "soccer"),
    Sport.TENNIS: ("tennis", "tennisquiz", "grandslam"),
    Sport.BADMINTON: ("badminton", "badmintonlovers", "shuttle"),
    Sport.BASKETBALL: ("basketball", "nba", "hoops"),
    Sport.HOCKEY: ("hockey", "fieldhockey", "hockeyindia"),
    Sport.ATHLETICS: ("athletics", "trackandfield", "running"),
    Sport.FORMULA1: ("formula1", "f1", "motorsport"),
    Sport.KABADDI: ("kabaddi", "prokabaddi", "kabaddilovers"),
    Sport.CHESS: ("chess", "chesslovers", "chesspuzzle"),
}

_TYPE_TAGS: dict[ContentType, tuple[str, ...]] = {
    ContentType.MCQ: ("sportsquiz", "quiztime"),
    ContentType.TRUE_FALSE: ("truefalse", "sportstrivia"),
    ContentType.POLL: ("thisorthat", "yourcall"),
    ContentType.FILL_BLANK: ("fillintheblank", "sportstrivia"),
    ContentType.GUESS_NUMBER: ("guessthenumber", "sportsstats"),
}

_CTA: dict[ContentType, str] = {
    ContentType.MCQ: "Tap your answer 👆",
    ContentType.TRUE_FALSE: "True or false? Vote now 👆",
    ContentType.POLL: "Pick a side 👆 No wrong answers.",
    ContentType.FILL_BLANK: "Fill in the blank 👇",
    ContentType.GUESS_NUMBER: "Drop your guess in the comments 👇",
}


# --------------------------------------------------------------------- payload


def _prompt_text(item: BaseItem) -> str:
    if isinstance(item, (MCQItem, GuessNumberItem)):
        return item.question
    if isinstance(item, TrueFalseItem):
        return item.statement
    if isinstance(item, PollItem):
        return item.prompt
    if isinstance(item, FillBlankItem):
        return item.sentence
    return ""


def _option_texts(item: BaseItem) -> list[str]:
    if isinstance(item, (MCQItem, FillBlankItem, PollItem)):
        return list(item.options)
    if isinstance(item, TrueFalseItem):
        return ["True", "False"]
    if isinstance(item, GuessNumberItem):
        return []  # free-text guess
    return []


def build_caption(item: BaseItem) -> str:
    """A ready-to-paste caption, sized for the feed."""
    lines: list[str] = []
    prompt = _prompt_text(item)

    if isinstance(item, FillBlankItem):
        lines.append(prompt.replace(BLANK_TOKEN, "______"))
    else:
        lines.append(prompt)

    if isinstance(item, PollItem):
        lines.append(f"{item.options[0]} or {item.options[1]}?")
    elif isinstance(item, GuessNumberItem):
        lines.append(f"Closest guess wins — within ±{item.range_label.split('±')[-1]}")

    lines.append(_CTA.get(item.content_type, "Tell us what you think 👇"))
    return clip("\n\n".join(l for l in lines if l), INSTAGRAM_LIMITS["caption"])


def build_hashtags(item: BaseItem, limit: int = 6) -> list[str]:
    tags = [
        *_SPORT_TAGS.get(item.sport, (item.sport.value.lower().replace(" ", ""),)),
        *_TYPE_TAGS.get(item.content_type, ()),
        "stapubox",
    ]
    seen: set[str] = set()
    unique: list[str] = []
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            unique.append(f"#{tag}")
    return unique[:limit]


def build_instagram_payload(item: BaseItem) -> InstagramPayload:
    """Shape an item for Instagram, flagging anything that will truncate."""
    sticker, surface = SURFACE_MAP.get(
        item.content_type, ("Quiz sticker", InstagramSurface.STORY)
    )
    prompt = _prompt_text(item).strip()
    options = [o.strip() for o in _option_texts(item)]

    warnings: list[str] = []
    if len(prompt) > INSTAGRAM_LIMITS["prompt"]:
        warnings.append(
            f"Prompt is {len(prompt)} characters — Instagram displays roughly "
            f"{INSTAGRAM_LIMITS['prompt']} before truncating."
        )
    for option in options:
        if len(option) > INSTAGRAM_LIMITS["option"]:
            warnings.append(
                f"Option “{clip(option, 20)}” is {len(option)} characters — "
                f"keep options under {INSTAGRAM_LIMITS['option']}."
            )

    return InstagramPayload(
        sticker=sticker,
        surface=surface,
        prompt_text=prompt,
        option_texts=options,
        caption=build_caption(item),
        hashtags=build_hashtags(item),
        within_limits=not warnings,
        limit_warnings=warnings,
    )


# ----------------------------------------------------------------------- score


def score_breakdown(item: BaseItem) -> list[tuple[str, int]]:
    """Every contribution to the engagement score, for full transparency."""
    parts: list[tuple[str, int]] = []

    # Base rate by format. Polls need no knowledge to answer, so they attract
    # the widest participation; free-text guesses drive comments, which weigh
    # more heavily in ranking than taps.
    base = {
        ContentType.POLL: 46,
        ContentType.GUESS_NUMBER: 40,
        ContentType.TRUE_FALSE: 38,
        ContentType.MCQ: 36,
        ContentType.FILL_BLANK: 34,
    }[item.content_type]
    parts.append(("format baseline", base))

    # Medium difficulty maximises participation: easy feels patronising, hard
    # discourages a guess.
    if item.content_type in {ContentType.POLL}:
        pass  # difficulty is meaningless for opinion content
    elif item.difficulty is Difficulty.MEDIUM:
        parts.append(("medium difficulty sweet spot", 12))
    elif item.difficulty is Difficulty.EASY:
        parts.append(("easy — high completion, low bragging rights", 8))
    else:
        parts.append(("hard — fewer answers, more debate", 6))

    payload = item.instagram
    if payload is not None:
        if payload.within_limits:
            parts.append(("fits Instagram sticker limits", 10))
        else:
            parts.append(("copy will truncate on Instagram", -8))

    prompt = _prompt_text(item)
    if prompt and len(prompt) <= 70:
        parts.append(("short, scannable prompt", 6))

    # Topical content outperforms evergreen trivia.
    if any(
        s.kind is SourceKind.WEB_SEARCH for s in item.grounding.resolved_sources
    ):
        parts.append(("grounded in fresh web results", 8))
    elif item.grounding.resolved_sources:
        parts.append(("grounded in knowledge base", 4))

    if item.content_type in {ContentType.MCQ, ContentType.FILL_BLANK}:
        if len({o.casefold() for o in _option_texts(item)}) == 4:
            parts.append(("four distinct, plausible options", 4))

    if isinstance(item, GuessNumberItem):
        # A tight range makes the guess feel like a real challenge.
        ratio = item.tolerance / abs(item.target) if item.target else 1.0
        if ratio <= 0.1:
            parts.append(("tight tolerance — genuine challenge", 6))

    if item.grounding.confidence == "low":
        parts.append(("low model confidence", -10))

    if item.explanation.strip():
        parts.append(("has a shareable explanation", 4))

    return parts


def score_engagement(item: BaseItem) -> int:
    """Clamp the heuristic total into 0-100."""
    total = sum(points for _, points in score_breakdown(item))
    return max(0, min(100, total))


# ---------------------------------------------------------------------- enrich


def enrich(item: BaseItem) -> BaseItem:
    """Attach the Instagram payload and engagement score, in that order.

    Order matters: the score rewards copy that fits the sticker limits, so the
    payload must exist first.
    """
    item.instagram = build_instagram_payload(item)
    item.engagement_score = score_engagement(item)
    return item


def batch_insights(items: list[BaseItem]) -> dict[str, object]:
    """Aggregate stats powering the dashboard's insights panel."""
    if not items:
        return {
            "count": 0,
            "average_score": 0,
            "best_item_id": None,
            "type_mix": {},
            "surface_mix": {},
            "grounded": 0,
            "opinion": 0,
            "truncation_warnings": 0,
        }

    type_mix: dict[str, int] = {}
    surface_mix: dict[str, int] = {}
    for item in items:
        type_mix[item.content_type.value] = type_mix.get(item.content_type.value, 0) + 1
        if item.instagram is not None:
            key = item.instagram.surface.value
            surface_mix[key] = surface_mix.get(key, 0) + 1

    best = max(items, key=lambda i: i.engagement_score)
    return {
        "count": len(items),
        "average_score": round(sum(i.engagement_score for i in items) / len(items)),
        "best_item_id": best.id,
        "type_mix": type_mix,
        "surface_mix": surface_mix,
        "grounded": sum(1 for i in items if i.grounding.is_grounded),
        "opinion": sum(1 for i in items if not i.grounding.fact_checked),
        "truncation_warnings": sum(
            1 for i in items if i.instagram and not i.instagram.within_limits
        ),
    }
