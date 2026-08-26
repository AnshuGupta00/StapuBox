"""Cross-session freshness: never serve the same fact twice.

The spec asks for content that stays fresh *across* requests, not just inside
one batch. A JSONL ledger on disk records every accepted item's fingerprint and
normalised text; the newest ``NOVELTY_LOOKBACK`` entries are held in memory and
consulted on every candidate.

Two levels of matching:

* **exact** — the fingerprint (a hash of the stopword-stripped, sorted token set)
  already catches rephrasings like "Who won the 1983 World Cup?" versus "The 1983
  World Cup was won by whom?";
* **fuzzy** — Jaccard overlap above :data:`SIMILARITY_THRESHOLD` catches the same
  fact dressed in extra words, which a hash cannot.

Recent prompts are also fed back into the generation template's *avoid* list, so
the model is steered away from repeats before it drafts them — the ledger is the
backstop, not the only defence.
"""

from __future__ import annotations

import json
import logging
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.config import Settings, get_settings
from app.utils.helpers import content_key, jaccard

logger = logging.getLogger(__name__)

#: Token-overlap ratio above which two items are considered the same fact.
SIMILARITY_THRESHOLD = 0.82

#: Fuzzy matching is O(n) per candidate, so only sweep the newest entries.
FUZZY_WINDOW = 120


@dataclass(frozen=True)
class LedgerEntry:
    fingerprint: str
    content_type: str
    text: str
    key: str
    created_at: str

    @classmethod
    def create(cls, fp: str, *, text: str, content_type: str) -> "LedgerEntry":
        return cls(
            fingerprint=fp,
            content_type=content_type,
            text=text,
            key=content_key(text),
            created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )

    def to_json(self) -> str:
        return json.dumps(
            {
                "fingerprint": self.fingerprint,
                "content_type": self.content_type,
                "text": self.text,
                "created_at": self.created_at,
            },
            ensure_ascii=False,
        )


class NoveltyLedger:
    """Append-only history of what has already been generated.

    Satisfies the ``NoveltyGuard`` protocol the generators depend on. Every
    failure mode is non-fatal: an unreadable or unwritable ledger degrades to
    in-memory-only dedup rather than breaking generation.
    """

    def __init__(
        self, path: Path | None = None, lookback: int | None = None
    ) -> None:
        settings: Settings = get_settings()
        self.path = Path(path) if path else settings.history_path
        self.lookback = lookback if lookback is not None else settings.novelty_lookback
        self._lock = threading.Lock()
        self._entries: deque[LedgerEntry] = deque(maxlen=max(self.lookback, 1))
        self._fingerprints: set[str] = set()
        self._writable = True
        self._load()

    # ---------------------------------------------------------------- lifecycle

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            logger.warning("Could not read novelty ledger %s: %s", self.path, exc)
            return

        # Only the newest window matters, so parse from the tail.
        for line in lines[-max(self.lookback, 1) :]:
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                continue  # tolerate a truncated final write
            text = raw.get("text", "")
            fp = raw.get("fingerprint", "")
            if not fp:
                continue
            self._entries.append(
                LedgerEntry(
                    fingerprint=fp,
                    content_type=raw.get("content_type", ""),
                    text=text,
                    key=content_key(text),
                    created_at=raw.get("created_at", ""),
                )
            )
        self._rebuild_index()
        logger.debug("Novelty ledger loaded with %d entries", len(self._entries))

    def _rebuild_index(self) -> None:
        self._fingerprints = {e.fingerprint for e in self._entries}

    # -------------------------------------------------------- NoveltyGuard API

    def is_duplicate(self, fp: str, *, text: str = "") -> bool:
        with self._lock:
            if fp in self._fingerprints:
                return True
            if not text.strip():
                return False
            for entry in list(self._entries)[-FUZZY_WINDOW:]:
                if jaccard(text, entry.text) >= SIMILARITY_THRESHOLD:
                    logger.debug("Near-duplicate of %s", entry.fingerprint)
                    return True
        return False

    def remember(self, fp: str, *, text: str, content_type: str = "") -> None:
        entry = LedgerEntry.create(fp, text=text, content_type=content_type)
        with self._lock:
            evicted = len(self._entries) == self._entries.maxlen
            self._entries.append(entry)
            if evicted:
                # The deque silently dropped its oldest entry; rebuild the
                # fingerprint index so it cannot grow without bound.
                self._rebuild_index()
            else:
                self._fingerprints.add(fp)
            self._append_to_disk(entry)

    def _append_to_disk(self, entry: LedgerEntry) -> None:
        if not self._writable:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(entry.to_json() + "\n")
        except OSError as exc:
            # Dedup still works for this process; only persistence is lost.
            self._writable = False
            logger.warning(
                "Novelty ledger is read-only (%s); dedup is in-memory only", exc
            )

    # ------------------------------------------------------------------ queries

    def recent_texts(self, *, content_type: str = "", limit: int = 12) -> list[str]:
        """Recent prompts, newest last, for the template's *avoid* block."""
        with self._lock:
            entries = [
                e
                for e in self._entries
                if not content_type or e.content_type == content_type
            ]
        return [e.text for e in entries[-limit:]]

    def stats(self) -> dict[str, object]:
        with self._lock:
            by_type: dict[str, int] = {}
            for entry in self._entries:
                by_type[entry.content_type] = by_type.get(entry.content_type, 0) + 1
            return {
                "tracked": len(self._entries),
                "lookback": self.lookback,
                "by_type": by_type,
                "path": str(self.path),
                "persisted": self._writable,
            }

    def clear(self) -> None:
        """Forget everything, including on disk. Used by tests."""
        with self._lock:
            self._entries.clear()
            self._fingerprints.clear()
            try:
                if self.path.exists():
                    self.path.unlink()
            except OSError:  # pragma: no cover - best effort
                pass
            self._writable = True


_ledger: NoveltyLedger | None = None


def get_ledger() -> NoveltyLedger:
    """Process-wide singleton so every request shares one history."""
    global _ledger
    if _ledger is None:
        _ledger = NoveltyLedger()
    return _ledger
