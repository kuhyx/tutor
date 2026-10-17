# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The event-log fold: a pure function of the events, the same in Dart.

``DOCS-contract-curriculum.md`` §4/§5, step by step:

1. merge every device's events and sort them by ``(at, eid)``;
2. drop a ``review`` that comes less than 60 s after an earlier *kept*
   review of the same card from a *different* device (an offline double tap
   on two phones); the same device rating twice is kept;
3. per card: ``taught`` starts a NEW FSRS card reviewed Good at ``at``
   (re-teaching resets it), ``untaught`` takes the card out of the queue, a
   ``review`` on an untaught card is ignored;
4. a review applies whatever its ``rev`` (knowledge, not wording);
5. ``flag`` events are remembered by ``rev``; a card is flagged while one
   matches its current rev, so an edit (rev + 1) clears its flags;
6. a drill review (``src: "drill"``, or any review by a device that wrote a
   ``taught``/``untaught``: the worker, whose only reviews are drill picks)
   schedules like any other but never sets ``app_good`` (§6 ``reviewed``).

``contract/fsrs_vectors.json`` (``fsrs_vectors.py``) pins the results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Final

import fsrs

from tutor.curriculum.eventlog import DRILL

if TYPE_CHECKING:
    from collections.abc import Iterable

DEDUPE_MS: Final = 60_000
WORKER_KINDS: Final = frozenset({"taught", "untaught"})
EPOCH: Final = datetime(1970, 1, 1, tzinfo=UTC)
_MS: Final = timedelta(milliseconds=1)
SCHEDULER: Final = fsrs.Scheduler(
    desired_retention=0.9,
    learning_steps=(),
    relearning_steps=(),
    maximum_interval=36500,
    enable_fuzzing=False,
)
Ref = tuple[str, str]  # (subject, card)


def to_dt(ms: int) -> datetime:
    """Unix ms -> aware UTC datetime, exactly (no float rounding)."""
    return EPOCH + timedelta(milliseconds=ms)


def to_ms(when: datetime) -> int:
    """Aware datetime -> unix ms."""
    return (when - EPOCH) // _MS


@dataclass
class CardFold:
    """One card's folded history."""

    taught_at: int | None = None  # the last ``taught``; None while untaught
    session: str = ""
    memory: fsrs.Card | None = None
    reviews: list[tuple[int, int]] = field(default_factory=list)  # since taught
    flag_revs: set[int] = field(default_factory=set)
    new_at: list[int] = field(default_factory=list)  # taught while untaught
    app_good: bool = False  # a non-drill review >= Good since taught

    @property
    def taught(self) -> bool:
        """Whether the card is taught (in the review queue)."""
        return self.taught_at is not None

    def flagged(self, rev: int) -> bool:
        """Whether a flag matches the card's current ``rev``."""
        return rev in self.flag_revs

    def fsrs_state(self) -> dict[str, Any] | None:
        """``{"due","stability","difficulty","state"}`` or None if untaught."""
        if self.memory is None:
            return None
        return {
            "due": to_ms(self.memory.due),
            "stability": self.memory.stability,
            "difficulty": self.memory.difficulty,
            "state": self.memory.state.name.lower(),
        }


@dataclass
class Fold:
    """The fold of the whole log: per-card state plus what was kept."""

    cards: dict[Ref, CardFold] = field(default_factory=dict)
    kept: list[dict[str, Any]] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)  # cross-device duplicates
    ignored: list[str] = field(default_factory=list)  # reviews of untaught cards

    def card(self, subject: str, card: str) -> CardFold:
        """The card's fold (an empty, untaught one if it never appeared)."""
        return self.cards.get((subject, card)) or CardFold()

    def taught_ids(self, subject: str) -> set[str]:
        """Ids of the subject's taught cards."""
        return {c for (s, c), f in self.cards.items() if s == subject and f.taught}


def _review(state: CardFold, at: int, rating: int, *, drill: bool = False) -> None:
    # None only right after ``_teach`` cleared it: a new card, due at once.
    memory = state.memory or fsrs.Card(card_id=1, due=to_dt(at))
    state.memory, _ = SCHEDULER.review_card(memory, fsrs.Rating(rating), to_dt(at))
    state.reviews.append((at, rating))
    state.app_good = state.app_good or (not drill and rating >= fsrs.Rating.Good)


def workers(events: Iterable[dict[str, Any]]) -> set[str]:
    """Devices that wrote a ``taught``/``untaught``: the PC worker(s)."""
    return {e["dev"] for e in events if e["k"] in WORKER_KINDS}


def is_drill(event: dict[str, Any], worker_devs: set[str]) -> bool:
    """A drill pick: tagged ``src: drill``, or (older picks) by a worker."""
    return event.get("src") == DRILL or event["dev"] in worker_devs


def _teach(state: CardFold, event: dict[str, Any]) -> None:
    at = int(event["at"])
    if state.taught_at is None:
        state.new_at.append(at)
    state.taught_at, state.session = at, str(event.get("session", ""))
    state.memory, state.reviews = None, []
    _review(state, at, int(fsrs.Rating.Good))
    state.reviews, state.app_good = [], False  # Good-at-taught is no recall


def _duplicate(recent: list[dict[str, Any]], event: dict[str, Any]) -> bool:
    """A review < 60 s after a kept review of the card from another device."""
    return any(
        k["dev"] != event["dev"] and event["at"] - k["at"] < DEDUPE_MS for k in recent
    )


def fold(events: Iterable[dict[str, Any]]) -> Fold:
    """Fold clean events (``eventlog.parse`` output) into per-card state."""
    out = Fold()
    recent: dict[Ref, list[dict[str, Any]]] = {}
    events = list(events)
    worker_devs = workers(events)  # the whole log first: order cannot matter
    for event in sorted(events, key=lambda e: (e["at"], e["eid"])):
        ref: Ref = (event["s"], event["c"])
        state = out.cards.setdefault(ref, CardFold())
        kind = event["k"]
        if kind == "review":
            if not state.taught:
                out.ignored.append(event["eid"])
                continue
            if _duplicate(recent.get(ref, []), event):
                out.dropped.append(event["eid"])
                continue
            recent[ref] = [
                *(k for k in recent.get(ref, []) if event["at"] - k["at"] < DEDUPE_MS),
                event,
            ]
            drill = is_drill(event, worker_devs)
            _review(state, event["at"], event["r"], drill=drill)
        elif kind == "taught":
            _teach(state, event)
        elif kind == "untaught":
            state.taught_at, state.memory, state.reviews = None, None, []
            state.app_good = False
        else:
            state.flag_revs.add(int(event["rev"]))
        out.kept.append(event)
    return out
