# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The pre-curriculum card source: ``deck/*.json`` + ``progress.json``.

Split out of ``source`` (file-length cap); ``source`` uses it in
``source_for`` while a data dir has not been migrated.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from tutor import gating
from tutor.cards import DECK_DIR, Card, load_deck
from tutor.curriculum import profiles
from tutor.curriculum.errors import NO_CARD_LEFT, RequestError

if TYPE_CHECKING:
    from tutor.store import Store

DEFAULT_SUBJECT: Final = "automation"
_NO_PATHS: Final[dict[str, dict[str, Any]]] = {}


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

    def waived(self) -> frozenset[str]:
        """The old deck has no phase gate."""
        return gating.NONE

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

    def path(self, card_id: str) -> dict[str, Any] | None:
        """The old deck has no paths."""
        return _NO_PATHS.get(card_id)

    def master(self, names: list[str], card_id: str, session: str) -> list[str]:
        """``progress.json`` ``mastered``."""
        return self.store.master(names, card_id, session)
