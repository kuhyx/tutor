# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Where the engine's cards come from: a curriculum subject or the old deck.

:class:`SubjectSource` serves a migrated / generated subject: the next card is
the curriculum pick (``rules.pick``: unlocked + ready modules, card gating,
the daily cap of 10 new cards), ``card_done`` appends a ``taught`` event, and
concepts go to the subject's ``concepts.json``. :class:`DeckSource` is the
pre-curriculum behaviour (``deck/*.json`` + ``progress.json``), used while a
data dir has not been migrated. Both keep ``progress.json`` ``cards_done`` in
step, so the history and progress views read the same done-set.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Protocol

from tutor import gating
from tutor.cards import Card, load_deck
from tutor.curriculum import card_rules, profiles, rules
from tutor.curriculum.errors import BAD_REQUEST, NO_CARD_LEFT, RequestError
from tutor.curriculum.eventlog import worker_event
from tutor.curriculum.subject_store import LOCK, Change

if TYPE_CHECKING:
    from tutor.curriculum.context import Context
    from tutor.curriculum.profiles import Profile
    from tutor.store import Store

DECK_DIR: Final = Path(__file__).resolve().parents[2] / "subjects/automation/deck"
DEFAULT_SUBJECT: Final = "automation"


class CardSource(Protocol):
    """What the engine needs from a subject."""

    subject: str
    profile: Profile

    def cards(self) -> list[Card]:
        """Every card that can be taught or listed."""

    def done(self) -> dict[str, dict[str, Any]]:
        """Taught card id -> ``{"session": sid}`` (at least)."""

    def pick(self, card_id: str | None, skip: str = "") -> Card:
        """The card a session opens (raises ``ValueError`` / ``RequestError``)."""

    def mark(self, card_id: str, session: str, *, done: bool) -> None:
        """Record a card taught (``done``) or taken back."""

    def mastered(self) -> list[str]:
        """Mastered concept names, oldest first."""

    def master(self, names: list[str], card_id: str, session: str) -> list[str]:
        """Record concepts; returns the new ones."""


class DeckSource:
    """The PLC deck and ``progress.json``, as before the curriculum."""

    subject = DEFAULT_SUBJECT

    def __init__(self, store: Store, deck: list[Card] | None = None) -> None:
        """The given deck, else the repo deck."""
        self.store = store
        self.profile = profiles.automation()
        self._deck = deck if deck is not None else load_deck(DECK_DIR)

    def cards(self) -> list[Card]:
        """The whole deck."""
        return self._deck

    def done(self) -> dict[str, dict[str, Any]]:
        """``progress.json`` ``cards_done``."""
        found: dict[str, dict[str, Any]] = self.store.progress()["cards_done"]
        return found

    def pick(self, card_id: str | None, skip: str = "") -> Card:
        """``gating.pick`` (``skip``: the first open card other than it)."""
        if skip and not card_id:
            found = gating.first_open(self._deck, self.done(), skip=skip)
            if found is None:
                msg = "no unfinished card left"
                raise RequestError(NO_CARD_LEFT, msg)
            return found
        return gating.pick(self._deck, self.done(), card_id)

    def mark(self, card_id: str, session: str, *, done: bool) -> None:
        """``progress.json`` only."""
        if done:
            self.store.finish_card(card_id, session)
        else:
            self.store.unfinish_card(card_id)

    def mastered(self) -> list[str]:
        """``progress.json`` ``mastered``."""
        return self.store.mastered()

    def master(self, names: list[str], card_id: str, session: str) -> list[str]:
        """``progress.json`` ``mastered``."""
        return self.store.master(names, card_id, session)


class SubjectSource:
    """One curriculum subject of the data dir."""

    def __init__(self, store: Store, ctx: Context, subject: str) -> None:
        """``ctx.clock`` must be the engine's clock (ms)."""
        self.store, self.ctx, self.subject = store, ctx, subject
        raw = ctx.subjects.profile_raw(subject)
        self.profile = (
            profiles.Profile.from_json(raw) if raw else profiles.generated(subject, {})
        )

    def _view(self) -> rules.View:
        plan = self.ctx.subjects.plan(self.subject)
        if plan is None:
            msg = f"{self.subject} has no plan yet"
            raise RequestError(BAD_REQUEST, msg)
        return rules.View(self.subject, plan, self.ctx.subjects.cards(self.subject))

    def cards(self) -> list[Card]:
        """Every non-suspended card of a module that has cards, in order."""
        view = self._view()
        return [
            card_rules.as_card(cid, rec, module)
            for module in view.plan.modules
            for cid, rec in view.module_cards(module.id)
            if not rec.suspended
        ]

    def done(self) -> dict[str, dict[str, Any]]:
        """The fold's taught cards."""
        folded = self.ctx.fold()
        return {
            cid: {"session": folded.card(self.subject, cid).session}
            for cid in folded.taught_ids(self.subject)
        }

    def pick(self, card_id: str | None, skip: str = "") -> Card:
        """``rules.pick`` over the subject (``skip`` left out of the pick)."""
        view = self._view()
        if skip and not card_id:
            kept = {k: v for k, v in view.cards.items() if k != skip}
            view = rules.View(view.subject, view.plan, kept)
        chosen = rules.pick(view, self.ctx.fold(), card_id, self.ctx.clock())
        return next(c for c in self.cards() if c.id == chosen)

    def mark(self, card_id: str, session: str, *, done: bool) -> None:
        """A ``taught`` / ``untaught`` event, mirrored into ``progress.json``."""
        kind = "taught" if done else "untaught"
        ref = (self.subject, card_id)
        at = self.ctx.clock()
        self.ctx.log.append(
            [worker_event(kind, ref, dev=self.ctx.device, at=at, session=session)]
        )
        if done:
            self.store.finish_card(card_id, session)
        else:
            self.store.unfinish_card(card_id)

    def mastered(self) -> list[str]:
        """The subject's ``concepts.json`` names."""
        return [str(c.get("name")) for c in self.ctx.subjects.concepts(self.subject)]

    def master(self, names: list[str], card_id: str, session: str) -> list[str]:
        """Append the new names to ``concepts.json``."""
        with LOCK:
            meta = self.ctx.subjects.need_meta(self.subject)
            concepts = self.ctx.subjects.concepts(self.subject)
            have = {c.get("name") for c in concepts}
            fresh = list(dict.fromkeys(n for n in names if n not in have))
            at = self.ctx.clock()
            if fresh:
                added = [
                    {"name": n, "at": at, "card": card_id, "session": session}
                    for n in fresh
                ]
                self.ctx.subjects.commit(
                    self.subject, meta, Change(concepts=[*concepts, *added])
                )
        return fresh


def source_for(store: Store, ctx: Context, subject: str | None = None) -> CardSource:
    """The subject's source; the old deck while ``automation`` is unmigrated."""
    name = subject or DEFAULT_SUBJECT
    if ctx.subjects.meta(name) is not None:
        return SubjectSource(store, ctx, name)
    if name == DEFAULT_SUBJECT:
        return DeckSource(store)
    msg = f"unknown subject {name!r}"
    raise RequestError(BAD_REQUEST, msg)
