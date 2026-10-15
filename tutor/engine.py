# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The session engine: model turns in, clock / credit / store / media wired up.

Every event reaches the engagement clock as it happens; the model supplies only
``low_effort`` and check grades. Each released minute is credited (``unit_credit``)
and claimed once the ledger reads it back. Card end, Next, Stop: ``cardflow``.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
import time
from typing import TYPE_CHECKING, Any
import uuid

from tutor import backfill, gating, media, picked, repair, resume, unit_credit
from tutor import cards as cards_mod
from tutor.cardflow import CardFlow
from tutor.clock import EngagementClock, reply_time
from tutor.conversation import Conversation
from tutor.curriculum.source import CardSource, source_for
from tutor.delivery import DESKTOP, Delivery, learner_message, note_lines
from tutor.prompt import engine_note, system_prompt, wrap_learner
from tutor.session import TutorSession, isolated_options
from tutor.store import Store

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from tutor.clock import BlockReady


class Engine(CardFlow):
    """One study session at a time, for one learner."""

    def __init__(
        self,
        *,
        store: Store | None = None,
        now: Callable[[], float] = time.time,
        credit_fn: Callable[[list[BlockReady], str], list[dict[str, Any]]]
        | None = None,
        session_factory: Callable[[str], TutorSession] | None = None,
        simulated_time: bool = False,
    ) -> None:
        """Wire the collaborators; ``simulated_time`` lets a driver skip ahead."""
        self.store = store or Store()
        self._now = now
        self._credit = credit_fn or (
            lambda units, sid: unit_credit.credit_units(units, sid, now=self.time())
        )
        self._factory = session_factory or (
            lambda prompt: TutorSession(isolated_options(prompt))
        )
        self.simulated = simulated_time
        self._offset = 0.0
        self._lock = asyncio.Lock()
        self.source: CardSource = source_for(self.store, self.ctx)
        self.card: cards_mod.Card | None = None
        self._minutes = ("", 0)  # (local day, ledger total that day)
        self._session: TutorSession | None = None
        self._conv: Conversation | None = None

    @property
    def session_id(self) -> str:
        """The live session's id, or ``""`` before the first start."""
        return self._conv.session_id if self._conv else ""

    @property
    def messages(self) -> list[dict[str, Any]]:
        """The page messages of the live session, oldest first."""
        return self._conv.messages if self._conv else []

    @property
    def receipts(self) -> list[dict[str, Any]]:
        """One row per credit attempt of the live session."""
        return self._conv.receipts if self._conv else []

    def time(self) -> float:
        """The engine's clock (wall time plus any simulated skip)."""
        return self._now() + self._offset

    def cards(self) -> list[dict[str, Any]]:
        """Every card, done or not, and what still locks it (``gating``)."""
        return gating.listing(self.deck, self.source.done())

    async def start(
        self,
        card_id: str | None = None,
        subject: str | None = None,
        *,
        device: str = DESKTOP,
    ) -> dict[str, Any]:
        """Begin a session on ``card_id`` (default: the subject's next card).

        ``subject`` switches the subject first, ``device`` is where it opened.
        An unknown or locked card, or the daily new-card cap, raises
        ``ValueError`` (``RequestError``) before the live session is touched.
        """
        async with self._lock:
            src = self._source_for(subject)
            card = src.pick(card_id)  # raises before anything changes
            self.source = src
            if self._session is not None:
                await self._session.close()
            self.card = card
            sid = f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}"
            self._conv = Conversation(sid, card.id, EngagementClock(self.time()))
            self._session = self._factory(self._prompt(card))
            start = {"type": "start", "card": card.id, "subject": self.source.subject}
            self.store.log(self.session_id, {**start, "device": device})
            await self._turn("Begin the session.", learner_text=None, device=device)
        return self.state()

    def repair_done_cards(self) -> list[tuple[str, str]]:
        """Run the one-off card_done repair (see ``repair``)."""
        return repair.repair_done_cards(self.store)

    def backfill_today(self) -> None:
        """Credit minutes today's transcripts earned but never got paid (idempotent)."""
        paid = backfill.backfill_day(
            self.store.root / "sessions",
            time.strftime("%Y%m%d"),
            self._credit,
            self.store.log,
        )
        self._set_today(max(self.minutes_today, paid))

    def resume_latest(self) -> bool:
        """Pick today's newest session back up after a restart (see ``resume_path``)."""
        path = resume.latest_today(
            self.store.root / "sessions", time.strftime("%Y%m%d")
        )
        return self.resume_path(path) if path else False

    def resume_path(self, path: Path) -> bool:
        """Resume ``path``; the model starts primed on next reply (``False``: none)."""
        state = resume.replay(path)
        conv = state.conversation if state else None
        src = self._resume_source(path)
        card = next((c for c in src.cards() if conv and c.id == conv.card_id), None)
        if state is None or conv is None or card is None or conv.stopped:
            return False
        self.source, self.card, self._conv = src, card, conv
        # max: backfill_today may already have paid more than these receipts saw.
        self._set_today(
            max(self.minutes_today, unit_credit.minutes_today(conv.receipts))
        )
        self._session = self._factory(self._prompt(card))
        conv.resumed.note = resume.primer(conv.messages)
        conv.clock.server_restarted(self.time())
        self.store.log(self.session_id, {"type": "resume", "t": self.time()})
        # Top-up: minutes no row paid yet; a span's entry id is deterministic,
        # so a retry rewrites the same row and never doubles.
        self._record(state.unrecorded)
        return True

    async def reply(
        self,
        text: str,
        advance_s: float = 0.0,
        msg_id: str = "",
        via: Delivery | None = None,
    ) -> dict[str, Any]:
        """The learner answers; returns the new state (a resent ``msg_id``: no-op).

        ``via``: Send press, relay receipt, device (``tutor.delivery``).
        """
        via = via or Delivery()
        async with self._lock:
            _, conv, _ = self._live()
            if msg_id and msg_id == conv.resumed.answered_id:
                return self.state()
            if self.simulated:
                self._offset += max(0.0, advance_s)
            got = self.time() if via.received is None else via.received
            t = reply_time(got, via.sent_at)
            await self._turn(
                text, learner_text=text, msg_id=msg_id, t_learner=t, device=via.device
            )
            conv.resumed.answered_id = msg_id
        return self.state()

    async def close(self) -> None:
        """Stop the model process."""
        if self._session is not None:
            await self._session.close()
            self._session = None

    def _prompt(self, card: cards_mod.Card) -> str:
        """The subject's system prompt for ``card``."""
        src = self.source
        return system_prompt(card, src.mastered(), src.profile)

    def _live(self) -> tuple[TutorSession, Conversation, cards_mod.Card]:
        """The running session, or RuntimeError before any start."""
        if self._session is None or self._conv is None or self.card is None:
            msg = "no session started"
            raise RuntimeError(msg)
        return self._session, self._conv, self.card

    async def _turn(
        self,
        prompt_text: str,
        *,
        learner_text: str | None,
        msg_id: str = "",
        t_learner: float | None = None,
        device: str = DESKTOP,
    ) -> None:
        session, conv = self._live()[:2]
        resume.reprime(conv, session.restarts)
        t_learner = self.time() if t_learner is None else t_learner
        active = conv.clock.active_seconds
        tap = conv.check.open and picked.tapped(learner_text or "")
        note = engine_note(
            active,
            active - conv.check.mark,
            check_open=conv.check.open,
            notes=[*conv.notes, *note_lines(device), *picked.note(tap=tap)],
            attempt=conv.check.attempt or 1,
        )
        body = wrap_learner(prompt_text) if learner_text else prompt_text
        if conv.resumed.note:
            body = f"{conv.resumed.note}\n{body}"
        if learner_text is not None:
            self.store.log(
                self.session_id,
                {"type": "learner", "text": learner_text, "note": note}
                | {"t": t_learner, "msg_id": msg_id, "device": device},
            )
        turn, _ = await session.ask(f"{note}\n{body}")
        if not self.source.profile.diagrams:  # schemdraw draws circuits only
            turn = replace(turn, diagram=None)
        # Only now: a failed ask leaves no learner bubble (the page keeps the
        # text for a retry) and keeps the notes and primer for that retry.
        conv.notes, conv.resumed.note = [], ""
        if learner_text is not None:
            conv.messages.append(learner_message(learner_text, device))
        message = media.page_message(turn)
        await media.attach(media.Turn(session, conv, self.store), turn, message)
        # Stamped when the final message (after any image check) is ready, so
        # the check's model call never eats into the learner's reply window.
        t_tutor = self.time()
        if learner_text is not None:
            conv.clock.user_reply(t_learner, learner_text, low_effort=turn.low_effort)
        conv.clock.tutor_message(t_tutor)
        self._apply(turn, t_tutor, message, tap=tap)
