"""Small, dependency-free helpers shared across the app."""

from __future__ import annotations

import hashlib
import re
import unicodedata

_PUNCT = re.compile(r"[^\w\s]")
_WS = re.compile(r"\s+")

#: Words that carry no identifying signal, dropped before fingerprinting so
#: "Who won the 1983 World Cup?" and "The 1983 World Cup was won by whom?"
#: collapse to the same fingerprint.
_STOPWORDS = frozenset(
    """
    a an the is are was were be been being do does did who whom whose what which
    when where why how many much of in on at to for from by with and or not no
    this that these those it its as has have had he she they his her their
    """.split()
)


def normalize(text: str) -> str:
    """Lowercase, strip accents and punctuation, collapse whitespace."""
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in decomposed if not unicodedata.combining(c))
    lowered = _PUNCT.sub(" ", ascii_text.casefold())
    return _WS.sub(" ", lowered).strip()


def content_key(text: str) -> str:
    """A word-order-independent signature of the meaningful terms in ``text``."""
    tokens = [t for t in normalize(text).split() if t not in _STOPWORDS]
    # Sorting makes the key insensitive to rephrasing that reorders clauses.
    return " ".join(sorted(set(tokens)))


def fingerprint(text: str) -> str:
    """Stable short hash used for cross-session duplicate detection."""
    return hashlib.sha256(content_key(text).encode("utf-8")).hexdigest()[:16]


def jaccard(a: str, b: str) -> float:
    """Token overlap between two strings, in ``[0, 1]``."""
    tokens_a = set(content_key(a).split())
    tokens_b = set(content_key(b).split())
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def clip(text: str, limit: int) -> str:
    """Trim to ``limit`` characters on a word boundary where possible."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[: limit - 1]
    if " " in cut[limit // 2 :]:
        cut = cut.rsplit(" ", 1)[0]
    return cut + "…"


def interleave(groups: list[list]) -> list:
    """Round-robin merge, used to mix content types evenly through a batch.

    ``[[a1, a2], [b1], [c1, c2]]`` -> ``[a1, b1, c1, a2, c2]``
    """
    merged: list = []
    index = 0
    remaining = True
    while remaining:
        remaining = False
        for group in groups:
            if index < len(group):
                merged.append(group[index])
                remaining = True
        index += 1
    return merged
