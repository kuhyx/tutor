# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The model-free drill: multiple choice on taught cards, for when Claude is not.

:meth:`Drill.next` picks a card already taught (the curriculum fold's taught
set, plus ``progress.json`` ``cards_done`` for ``automation``), due first and
oldest due first, and offers its ``back`` among up to three other backs,
the closest cards first (:mod:`tutor.distractors`).
:meth:`Drill.answer` grades it in code and appends one ``review`` event (Good
/ Again) to the event log in the app's shape, so the app's FSRS fold sees it
once the relay has pushed it.

Credit is the tutor's: a drill run is a session (``drill-<id>``, one per local
day), the prompt-to-answer gap accrues on an :class:`EngagementClock` like a
learner gap, right or wrong, and released minutes go through
``unit_credit.credit_units``. A pick under :data:`MIN_PICK_SECONDS` earns
nothing. The open prompt lives in memory only: after a restart, answering
it is :class:`PromptGoneError` (``unknown_prompt``), never a crash.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import logging
import time
from typing import TYPE_CHECKING, Any, Final
import uuid

from tutor import credit, unavailable, unit_credit
from tutor.clock import EngagementClock
from tutor.curriculum.errors import RequestError
from tutor.curriculum.eventlog import review_event
from tutor.curriculum.ids import ulid
from tutor.curriculum.source import DEFAULT_SUBJECT, source_for
from tutor.distractors import options_for

if TYPE_CHECKING:
    from tutor.cards import Card
    from tutor.curriculum.context import Context
    from tutor.curriculum.fold import Fold
    from tutor.store import Store

MIN_PICK_SECONDS: Final = 3.0  # a faster pick is a guess: it earns nothing
GOOD: Final = 3
AGAIN: Final = 1
# The clock's filler test is for typed replies; a pick is never filler.
_PICK_TEXT: Final = "multiple-choice pick"
_logger = logging.getLogger(__name__)


class PromptGoneError(LookupError):
    """The answered prompt is not open (answered, replaced, or lost on restart)."""

    @property
    def code(self) -> str:
        """The contract code ``relay.errors.classify`` reads."""
        return "unknown_prompt"


@dataclass(frozen=True)
class Prompt:
    """One open question: which card, its options and when it was shown."""

    prompt_id: str
    subject: str
    card: Card
    options: list[str]
    answer: int
    shown_at: float
    rev: int


@dataclass(frozen=True)
class _Taught:
    """A taught card, when it is due, and the cards distractors come from."""

    subject: str
    card: Card
    due_ms: int
    rev: int
    pool: list[Card]


@dataclass
class _Run:
    """One drill session: its id, local day and clock."""

    session_id: str
    day: str
    clock: EngagementClock


def _iso_ms(value: object) -> int:
    """An ISO time (``progress.json``) in unix ms; 0 when absent or unreadable."""
    try:
        return int(datetime.fromisoformat(str(value)).timestamp() * 1000)
    except ValueError:
        _logger.warning("progress.json time %r unreadable; drilled as oldest", value)
        return 0


class Drill:
    """The drill of one data dir; at most one prompt is open at a time."""

    def __init__(self, store: Store, ctx: Context) -> None:
        """``ctx.device`` signs the review events (the worker's own log)."""
        self.store, self.ctx = store, ctx
        self.pending: Prompt | None = None
        self._run: _Run | None = None
        self._answered: dict[tuple[str, str], int] = {}

    def next(self, subject: str | None, at: float) -> dict[str, Any]:
        """The next question (it replaces any open one), or ``{"empty": True}``."""
        found = self._taught(subject)
        if not found:
            return {"empty": True}
        item = min(found, key=lambda t: (t.due_ms, t.subject, t.card.id))
        card, pid = item.card, ulid(int(at * 1000))
        shown, answer = options_for(card, item.pool, pid)
        self.pending = Prompt(pid, item.subject, card, shown, answer, at, item.rev)
        self._log(self._run_for(at), {"type": "prompt", "id": pid, "card": card.id})
        window = unavailable.current(at)
        return {
            "prompt_id": pid,
            "card": {"subject": item.subject, "id": card.id, "front": card.front},
            "options": shown,
            "today": self._today(at),
            "unavailable": window and {"until": window.end, "reason": window.reason},
        }

    def answer(self, prompt_id: str, choice: int, at: float) -> dict[str, Any]:
        """Grade the pick, log its review, accrue and credit the gap."""
        prompt, run = self.pending, self._run
        if prompt is None or run is None or prompt.prompt_id != prompt_id:
            msg = "that drill question is no longer open; ask for the next one"
            raise PromptGoneError(msg)
        if not 0 <= choice < len(prompt.options):
            msg = f"choice {choice} is not one of the {len(prompt.options)} options"
            raise ValueError(msg)
        self.pending = None
        correct, card = choice == prompt.answer, prompt.card
        ref, span = (
            (prompt.subject, card.id),
            (int(prompt.shown_at * 1000), int(at * 1000)),
        )
        rating = GOOD if correct else AGAIN
        event = review_event(
            ref, rating, dev=self.ctx.device, span=span, rev=prompt.rev
        )
        self.ctx.log.append([event])
        self._answered[ref] = span[1]
        rows = self._accrue(run, prompt, at)
        self._log(run, {"type": "answer", "card": card.id, "correct": correct})
        return {
            "correct": correct,
            "answer_index": prompt.answer,
            "back": card.back,
            "excerpt": card.excerpt,
            "source": card.source,
            "minute_credited": any(r["recorded"] and r["minutes"] for r in rows),
            "today": self._today(at),
        }

    def _accrue(self, run: _Run, prompt: Prompt, at: float) -> list[dict[str, Any]]:
        """Shown -> picked is a learner gap; then close it (no tutor time here)."""
        clock = run.clock
        clock.tutor_message(prompt.shown_at)
        quick = at - prompt.shown_at < MIN_PICK_SECONDS
        clock.user_reply(at, _PICK_TEXT, low_effort=quick)
        clock.tutor_message(at)  # a zero "tutor gap": nothing accrues after a pick
        units = clock.ready_blocks()
        rows = unit_credit.credit_units(units, run.session_id, now=at) if units else []
        for row in rows:
            self._log(run, {"type": "credit", **row})
        return rows

    def _taught(self, subject: str | None) -> list[_Taught]:
        """Every taught card of ``subject`` (None: of every subject)."""
        folded = self.ctx.fold()
        names = [subject] if subject else self.ctx.subjects.subjects()
        if not subject and DEFAULT_SUBJECT not in names:
            names.append(DEFAULT_SUBJECT)  # the unmigrated deck
        return [item for name in names for item in self._of(name, folded)]

    def _of(self, name: str, folded: Fold) -> list[_Taught]:
        """``name``'s taught cards: the fold's, plus ``cards_done`` for automation."""
        src = source_for(self.store, self.ctx, name)
        try:
            pool = src.cards()
        except RequestError as err:  # a subject still drafting its plan
            _logger.warning("drill skips %s: %s", name, err.message)
            return []
        done = self.store.progress()["cards_done"]
        taught = set(src.done()) | (set(done) if name == DEFAULT_SUBJECT else set())
        records = self.ctx.subjects.cards(name)
        out: list[_Taught] = []
        for card in (c for c in pool if c.id in taught):
            state = folded.card(name, card.id).fsrs_state()
            due = state["due"] if state else _iso_ms(done.get(card.id, {}).get("at"))
            # A card with no FSRS state must still rotate once answered here.
            due = max(due, self._answered.get((name, card.id), 0))
            rec = records.get(card.id)
            out.append(_Taught(name, card, due, rec.rev if rec else 1, pool))
        return out

    def _run_for(self, at: float) -> _Run:
        """Today's run (a new session id each local day, and after a restart)."""
        day = credit.local_day(at)[0]
        if self._run is None or self._run.day != day:
            stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(at))
            sid = f"drill-{stamp}-{uuid.uuid4().hex[:4]}"
            self._run = _Run(sid, day, EngagementClock(at))
        return self._run

    def _today(self, at: float) -> dict[str, int]:
        """This run's active minutes today and the ledger's credited minutes."""
        run = self._run
        today = run is not None and run.day == credit.local_day(at)[0]
        active = run.clock.active_seconds if run is not None and today else 0.0
        credited = unit_credit.ledger_minutes_today(at)
        return {"active_min": int(active // 60), "credited_min": credited}

    def _log(self, run: _Run, event: dict[str, Any]) -> None:
        """Append to ``drill/<run>.jsonl`` (not ``sessions/``: History reads that)."""
        path = self.store.root / "drill" / f"{run.session_id}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps({"logged_at": time.time(), **event}, ensure_ascii=False)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
