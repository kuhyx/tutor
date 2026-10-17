# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""What happens around a card inside one session: its end, the next one, stop.

One card, one session. When the learner gives the card's answer the tutor
sets ``card_done`` and the page offers Next card (this session ends and a new
one starts on the next unfinished card) or Stop here (the session ends and is
never resumed). Older transcripts may still hold an in-session ``next_card``
switch; replay keeps reading those. ``Engine`` mixes this in; the
attributes it needs are declared below for the type checker.
"""

from __future__ import annotations

from dataclasses import asdict
import logging
from typing import TYPE_CHECKING, Any, Final

from tutor import continuing, credit, gating, picked, unit_credit
from tutor.curriculum.context import Context
from tutor.curriculum.errors import RequestError
from tutor.curriculum.source import source_for, transcript_subject
from tutor.delivery import DESKTOP

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Awaitable, Callable
    from pathlib import Path

    from tutor import cards as cards_mod
    from tutor.clock import BlockReady
    from tutor.conversation import Conversation
    from tutor.curriculum.source import CardSource
    from tutor.models import TutorTurn
    from tutor.session import TutorSession
    from tutor.store import Store

TARGET_MINUTES: Final = 60
_logger = logging.getLogger(__name__)


class CardFlow:
    """Turn application, crediting, ``next_card``, ``stop`` and ``state``."""

    if TYPE_CHECKING:
        store: Store
        card: cards_mod.Card | None
        source: CardSource
        _minutes: tuple[str, int]
        _session: TutorSession | None
        _conv: Conversation | None
        _lock: asyncio.Lock
        _factory: Callable[[str], TutorSession]
        _credit: Callable[[list[BlockReady], str], list[dict[str, Any]]]

        @property
        def session_id(self) -> str:
            """The live session's id (``Engine``)."""

        @property
        def messages(self) -> list[dict[str, Any]]:
            """The live session's page messages (``Engine``)."""

        @property
        def receipts(self) -> list[dict[str, Any]]:
            """The live session's credit rows (``Engine``)."""

        time: Callable[[], float]
        start: Callable[..., Awaitable[dict[str, Any]]]
        resume_path: Callable[[Path], bool]
        _live: Callable[[], tuple[TutorSession, Conversation, cards_mod.Card]]
        _turn: Callable[..., Awaitable[str]]

    @property
    def minutes_today(self) -> int:
        """Today's ledger total; 0 after midnight (no ``max`` carries yesterday's)."""
        day, minutes = self._minutes
        return minutes if day == credit.local_day(self.time())[0] else 0

    def _set_today(self, minutes: int) -> None:
        """Record ``minutes`` as today's ledger total, stamped with today."""
        self._minutes = (credit.local_day(self.time())[0], minutes)

    @property
    def ctx(self) -> Context:
        """The curriculum context on the engine's data dir and clock (ms)."""
        return Context(self.store.root, clock=lambda: int(self.time() * 1000))

    @property
    def deck(self) -> list[cards_mod.Card]:
        """The current subject's cards."""
        return self.source.cards()

    def _source_for(self, subject: str | None) -> CardSource:
        """``subject``'s cards: the live source when it is that subject."""
        if not subject or subject == self.source.subject:
            return self.source
        return source_for(self.store, self.ctx, subject)

    def _resume_source(self, path: Path | None) -> CardSource:
        """The source of a transcript's subject (the live one if unknown)."""
        try:
            return self._source_for(transcript_subject(path) if path else None)
        except RequestError as err:
            _logger.warning("resume: %s; staying on %s", err, self.source.subject)
            return self.source

    async def next_card(self, *, device: str = DESKTOP) -> dict[str, Any]:
        """End this session and start a NEW one (opened on ``device``).

        One card, one session (kuhy, 2026-10-10): the transcript, URL and
        history row each stay about a single card. The ended session logs the
        choice (``next_card``) and a ``stop``, so it is never resumed. Raises
        ``ValueError`` when no card is left, before anything changes. Locked
        cards (``gating``) are skipped, so a session resumed on a card that
        became locked steers to the first open one.
        """
        async with self._lock:
            _, conv, card = self._live()
            # Raises (no card left, daily cap) before the session changes.
            nxt = self.source.pick(None, skip=card.id)
            self.store.log(conv.session_id, {"type": "next_card", "card": nxt.id})
            self.store.log(conv.session_id, {"type": "stop"})
        return await self.start(nxt.id, device=device)

    async def resume_session(self, path: Path) -> dict[str, Any]:
        """Continue the session in ``path``; the live one is left, not stopped.

        Raises ``ValueError`` when it cannot be resumed (stopped, card gone).
        """
        async with self._lock:
            old = self._session
            if not self.resume_path(path):
                msg = "this session cannot be continued (stopped, or its card is gone)"
                raise ValueError(msg)
            if old is not None:
                await old.close()
        return self.state()

    async def continue_subject(self, subject: str | None) -> bool:
        """Make ``subject``'s open session live (``continuing``); ``False``: none.

        No subject: the live one. Raises ``RequestError`` for an unknown subject.
        """
        src = self._source_for(subject)
        if self._conv is not None and src.subject == self.source.subject:
            return True
        found = continuing.open_session(
            self.store.root / "sessions", src.subject, src.done()
        )
        if found is not None:
            await self.resume_session(found)
        return found is not None

    async def stop(self) -> dict[str, Any]:
        """End the live session for good (nothing live: a no-op)."""
        async with self._lock:
            if self._conv is not None:
                self.store.log(self._conv.session_id, {"type": "stop"})
            if self._session is not None:
                await self._session.close()
            self._session, self._conv, self.card = None, None, None
        return self.state()

    async def set_card_done(
        self, card_id: str, *, done: bool, subject: str | None = None
    ) -> dict[str, Any]:
        """Manual override: mark ``card_id`` done (or not); never touches credit.

        Raises ``ValueError`` for a card not in the deck, and for marking a
        locked card done (marking one not done is always allowed). Done on the
        live card opens the Next card / Stop here choice, like the tutor's own
        ``card_done``. Logged in the live transcript when the card belongs to it.
        """
        async with self._lock:
            src = self._source_for(subject)
            card = next((c for c in src.cards() if c.id == card_id), None)
            if card is None:
                msg = f"unknown card {card_id!r}"
                raise ValueError(msg)
            progress = src.done()
            conv, sid = (self._conv if src is self.source else None), ""
            if done:
                gating.refuse_locked(card, progress, "mark done")
                was = progress.get(card_id) or {}
                sid = conv.session_id if conv else str(was.get("session", "manual"))
            src.mark(card_id, sid, done=done)
            if conv is not None and card_id in conv.cards:
                conv.set_done(card_id, done=done)
                event = {"type": "card_done_manual", "card": card_id, "done": done}
                self.store.log(conv.session_id, event)
        return self.state()

    def state(self) -> dict[str, Any]:
        """Everything the page needs to draw itself."""
        conv = self._conv
        card = self.card
        return {
            "session_id": self.session_id,
            "card": {"id": card.id, "front": card.front} if card else None,
            "messages": self.messages,
            "clock": conv.clock.snapshot(self.time()) if conv else {},
            "credited_minutes": min(self.minutes_today, TARGET_MINUTES),
            "session_credited_minutes": unit_credit.paid_minutes(self.receipts),
            "target_minutes": credit.target_minutes(self.time()),
            "receipts": self.receipts,
            "mastered": self.source.mastered(),
            "check_open": bool(conv and conv.check.open),
            "card_done": bool(conv and conv.card_done),
        }

    def _apply(
        self, turn: TutorTurn, t: float, message: dict[str, Any], *, tap: bool = False
    ) -> None:
        _, conv, card = self._live()
        logged = asdict(turn)
        # A tapped check answer: no pass, no mastery, no card_done (picked.py).
        if tap and picked.refuse(logged, message, conv.check):
            conv.notes.append(picked.REFUSED)
        if not conv.apply_checks(logged, t):
            message["check"] = None  # a refused third attempt is never shown
        if not turn.low_effort and (mastered := logged["concepts_mastered"]):
            names = [c.strip().lower() for c in mastered if c.strip()]
            message["mastered_new"] = self.source.master(
                names, card.id, self.session_id
            )
        # Only a card_done reads progress.json: most turns end nothing.
        done = bool(logged["card_done"])
        need = gating.missing(card, self.source.done()) if done else []
        if need:  # locked: logged as refused, so replay and repair skip it
            logged["card_done"], logged["card_done_refused"] = False, need
            conv.notes.append(gating.refused_note(card, need))
        elif done:  # the tutor's word is enough (b193: a gate dropped it)
            if conv.mark_card_done():
                self.source.mark(card.id, self.session_id, done=True)
            message["card_done"] = True
        conv.messages.append(message)
        self.store.log(
            self.session_id, {"type": "tutor", "turn": logged, "ui": message, "t": t}
        )
        self._record(conv.clock.ready_blocks())

    def _record(self, units: list[BlockReady]) -> None:
        """Credit the minutes a turn released: one ledger row per span of them."""
        for row in self._credit(units, self.session_id) if units else []:
            if row["recorded"]:
                self._set_today(max(self.minutes_today, row["minutes_today"]))
            self.receipts.append(row)
            self.store.log(self.session_id, {"type": "credit", **row})
