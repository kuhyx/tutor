# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The module gate and the next-card pick (``DOCS-contract-curriculum.md`` §6).

The module gate (kuhy, 2026-11-22; no daily cap, no waiting): the first card
of a module with no taught card opens only once every earlier module is
fully taught with each card reviewed, and no card of the subject is due.
Due cards never block a module already started. The refusal lists the
exact cards that block (``gate_cards``), which the app reviews.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from tutor.curriculum.errors import UNKNOWN_CARD, RequestError
from tutor.curriculum.no_card import (
    Held,
    due_in_subject,
    due_now,
    locked,
    no_card_left,
)
from tutor.curriculum.rules import OPEN, counted, reviewed, unlocked

if TYPE_CHECKING:
    from tutor.curriculum.fold import Fold
    from tutor.curriculum.records import CardRec, Module
    from tutor.curriculum.rules import View


def _open(view: View, card: CardRec, fold: Fold) -> bool:
    """Not suspended and every required card taught."""
    taught = fold.taught_ids(view.subject)
    return not card.suspended and all(need in taught for need in card.requires)


@dataclass(frozen=True)
class Gate:
    """What stands before a new module (or the end of the plan).

    ``blocker``: the first earlier module with a taught card not yet
    reviewed; ``cards``: every such card plus the subject's cards due now
    (plan order, no repeats); ``writing``: an earlier module's cards are
    being generated; ``untaught``: an earlier open module still has an
    untaught card.
    """

    blocker: Module | None
    cards: list[str]
    writing: bool
    untaught: bool

    @property
    def clear(self) -> bool:
        """Nothing to review and nothing being written."""
        return not self.cards and not self.writing


def started(view: View, fold: Fold, module_id: str) -> bool:
    """Some card of the module (counted or not) was ever taught."""
    taught = fold.taught_ids(view.subject)
    return any(cid in taught for cid, _ in view.module_cards(module_id))


def gate(view: View, fold: Fold, now_ms: int, before: str | None = None) -> Gate:
    """The gate before module ``before`` (None: after the last module)."""
    blocker, cards, writing, untaught = None, [], False, False
    for module in view.plan.modules:
        if module.id == before:
            break
        if module.status == "generating":
            writing = True
            continue
        if module.status not in OPEN or not unlocked(view, module, fold):
            continue
        mine = counted(view, module.id, fold)
        untaught = untaught or any(not s.taught for _, s in mine)
        unpassed = [cid for cid, s in mine if s.taught and not reviewed(s)]
        if unpassed and blocker is None:
            blocker = module
        cards += unpassed
    cards += [cid for cid in due_now(view, fold, now_ms) if cid not in cards]
    return Gate(blocker, cards, writing, untaught)


def _first(view: View, fold: Fold, skip: str, now_ms: int) -> tuple[str, Module] | None:
    taught = fold.taught_ids(view.subject)
    for module in view.plan.modules:
        other = bool(view.only) and module.id != view.only
        held = other or module.status not in OPEN or module.id in view.refused
        if held or not unlocked(view, module, fold):
            continue
        for cid, card in view.module_cards(module.id):
            flagged = fold.card(view.subject, cid).flagged(card.rev)
            fresh = cid not in taught and cid != skip
            if not fresh or flagged or not _open(view, card, fold):
                continue
            if not started(view, fold, module.id):
                ahead = gate(view, fold, now_ms, before=module.id)
                if ahead.untaught and skip and not ahead.cards:
                    # Next skipped a module's last card: offer it again
                    # rather than jump to the next module.
                    return _first(view, fold, "", now_ms)
                if not ahead.clear:
                    raise _no_card(view, fold, now_ms, ahead)
            return cid, module
    return None


def _due_at(view: View, fold: Fold) -> int | None:
    """The earliest review due among the subject's counted cards."""
    states = [
        s.fsrs_state() for m in view.plan.modules for _, s in counted(view, m.id, fold)
    ]
    dues = [state["due"] for state in states if state is not None]
    return min(dues) if dues else None


def _no_card(
    view: View, fold: Fold, now_ms: int, ahead: Gate | None = None
) -> RequestError:
    """``no_card_left`` with the subject's title, its next step and its gate."""
    ahead = ahead or gate(view, fold, now_ms)
    err = no_card_left(
        view.title,
        module=ahead.blocker,
        due_at=_due_at(view, fold),
        writing=ahead.writing,
        now_ms=now_ms,
    )
    err.extra["subject_id"] = view.subject
    err.extra["due_in_subject"] = due_in_subject(view, fold, now_ms)
    err.extra["gate_cards"] = ahead.cards
    return err


def _to_unlock(view: View, module: Module, fold: Fold) -> Module | None:
    """The required module to review before ``module`` opens, if there is one.

    The first (plan order) not yet mastered, when it is ``ready``; None when
    the plan is unapproved, ``module`` is already unlocked or the blocker
    is not reviewable yet.
    """
    if view.plan.status != "approved" or unlocked(view, module, fold):
        return None
    need = next(
        (
            m
            for m in view.plan.modules
            if m.id in module.requires and m.status != "mastered"
        ),
        None,
    )
    return need if need is not None and need.status == "ready" else None


def _explicit(view: View, fold: Fold, card_id: str, now_ms: int) -> tuple[str, Module]:
    """``card_id`` and its module, if it can be taught now."""
    card = view.cards.get(card_id)
    if card is None:
        msg = f"unknown card {card_id!r} in {view.subject}"
        raise RequestError(UNKNOWN_CARD, msg)
    module = view.plan.module(card.module)
    if module is None:
        raise locked(
            view.title, card_id, subject=view.subject, module=None, held=Held()
        )
    ready = module.status in OPEN and unlocked(view, module, fold)
    if not ready or not _open(view, card, fold):
        need = _to_unlock(view, module, fold)
        raise locked(
            view.title, card_id, subject=view.subject, module=module, held=Held(need)
        )
    if module.id in view.refused:  # C3, before the gate: a review opens nothing
        raise _no_card(view, fold, now_ms)
    if not started(view, fold, module.id):
        ahead = gate(view, fold, now_ms, before=module.id)
        if ahead.cards or ahead.writing or ahead.untaught:
            raise locked(
                view.title,
                card_id,
                subject=view.subject,
                module=module,
                held=Held(ahead.blocker, ahead.cards, _due_at(view, fold)),
            )
    return card_id, module


def pick(
    view: View, fold: Fold, card_id: str | None, now_ms: int, skip: str = ""
) -> str:
    """The card a session teaches: ``card_id`` if open, else the next one.

    ``skip`` (no ``card_id``): never that card (Next card leaves it).

    Raises ``unknown_card``, ``locked`` or ``no_card_left`` (the module
    gate among them; also for a card of a ``view.refused`` module, C3).
    Re-teaching a taught card is free.
    """
    if card_id:
        return _explicit(view, fold, card_id, now_ms)[0]
    found = _first(view, fold, skip, now_ms)
    if found is None:
        raise _no_card(view, fold, now_ms)
    return found[0]
