# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Unlock, mastery, recall, the daily new-card cap and the next-card pick.

``DOCS-contract-curriculum.md`` §6, read from the folded log (never from FSRS
state): a card is *reviewed* once some app review since it was last taught
is Good or Easy (no time gap; a PC drill pick never counts,
``fold.is_drill``); a ``ready`` module whose counted cards (neither flagged
nor suspended, at least one) are all reviewed becomes ``mastered``
(and stays so); a module unlocks when the plan is approved and every module
it requires is mastered. *Good* (the latest review is Good or Easy, 20 h or
more after the teaching) and a module's *recall* (its good share) are shown
only: they no longer gate anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from tutor.credit import local_day
from tutor.curriculum.errors import DAILY_NEW_CAP, LOCKED, UNKNOWN_CARD, RequestError
from tutor.curriculum.no_card import no_card_left

if TYPE_CHECKING:
    from tutor.curriculum.fold import CardFold, Fold
    from tutor.curriculum.records import CardRec, Module, Plan

GOOD_GAP_MS: Final = 20 * 3600 * 1000
GOOD_RATING: Final = 3
NEW_CAP: Final = 10
OPEN: Final = frozenset({"ready", "mastered"})
WAITING: Final = frozenset({"locked", "failed"})  # pre-generated, not yet unlocked


@dataclass(frozen=True)
class View:
    """One subject's plan and cards, as read for a decision."""

    subject: str
    plan: Plan
    cards: dict[str, CardRec]
    title: str = ""  # shown instead of the slug (``no_card_left``)

    def module_cards(self, module_id: str) -> list[tuple[str, CardRec]]:
        """The module's cards in ``order``."""
        found = [(cid, c) for cid, c in self.cards.items() if c.module == module_id]
        return sorted(found, key=lambda item: item[1].order)


def good(state: CardFold) -> bool:
    """Taught, and the latest review since then is >= Good, 20 h or later."""
    if state.taught_at is None or not state.reviews:
        return False
    at, rating = state.reviews[-1]
    return rating >= GOOD_RATING and at >= state.taught_at + GOOD_GAP_MS


def reviewed(state: CardFold) -> bool:
    """Taught, and some app (not drill) review since then is >= Good, no gap."""
    return state.taught and state.app_good


def counted(view: View, module_id: str, fold: Fold) -> list[tuple[str, CardFold]]:
    """The module's cards that count: neither flagged nor suspended."""
    return [
        (cid, fold.card(view.subject, cid))
        for cid, card in view.module_cards(module_id)
        if not card.suspended and not fold.card(view.subject, cid).flagged(card.rev)
    ]


def recall(view: View, module_id: str, fold: Fold) -> float:
    """Good cards / cards neither flagged nor suspended (0 when none)."""
    states = [s for _, s in counted(view, module_id, fold)]
    return sum(good(s) for s in states) / len(states) if states else 0.0


def module_reviewed(view: View, module_id: str, fold: Fold) -> bool:
    """Every counted card reviewed; a module with none never is."""
    states = [s for _, s in counted(view, module_id, fold)]
    return bool(states) and all(reviewed(s) for s in states)


def unlocked(view: View, module: Module, fold: Fold) -> bool:
    """Plan approved and every required module mastered.

    A module with a taught card stays unlocked whatever happens to its
    prerequisites (the contract's grandfather rule for migrated modules).
    """
    if view.plan.status != "approved":
        return False
    taught = fold.taught_ids(view.subject)
    if any(cid in taught for cid, _ in view.module_cards(module.id)):
        return True
    status = {m.id: m.status for m in view.plan.modules}
    return all(status.get(need) == "mastered" for need in module.requires)


def advance_statuses(view: View, fold: Fold) -> list[str]:
    """Update recall and status in place (plan order); returns new unlocks.

    ``ready`` -> ``mastered`` once every counted card is reviewed
    (sticky; ``recall`` is written for display only); ``locked`` ->
    ``generating`` once unlocked, ``ready`` at once if its cards were
    pre-generated. Earlier modules are updated first, so a mastery unlocks
    its dependents in the same pass. An open module never carries an
    ``error`` (only ``failed`` does); a stale one is cleared.
    """
    unlocked_now = []
    for module in view.plan.modules:
        if module.status in OPEN:
            module.error = None
        module.recall = round(recall(view, module.id, fold), 4)
        if module.status == "ready" and module_reviewed(view, module.id, fold):
            module.status = "mastered"
        elif (
            module.pregenerated
            and module.status in WAITING
            and unlocked(view, module, fold)
        ):
            # Drafted ahead (``module_pregenerate``): open those cards and
            # never draft twice; a failed pre-generation drafts just in time.
            live = any(not c.suspended for _, c in view.module_cards(module.id))
            ready = module.status == "locked" and live
            module.status = "ready" if ready else "generating"
            module.pregenerated, module.error = False, None
            unlocked_now.append(module.id)
        elif module.status == "locked" and unlocked(view, module, fold):
            module.status = "generating"
            unlocked_now.append(module.id)
    return unlocked_now


def completed(plan: Plan) -> bool:
    """Approved and every module mastered."""
    return plan.status == "approved" and all(
        m.status == "mastered" for m in plan.modules
    )


def new_today(fold: Fold, now_ms: int) -> int:
    """Cards newly taught on today's PC-local date, all subjects."""
    today = local_day(now_ms / 1000)[0]
    return sum(
        local_day(at / 1000)[0] == today
        for state in fold.cards.values()
        for at in state.new_at
    )


def _open(view: View, card: CardRec, fold: Fold) -> bool:
    """Not suspended and every required card taught."""
    taught = fold.taught_ids(view.subject)
    return not card.suspended and all(need in taught for need in card.requires)


def _first(view: View, fold: Fold, skip: str) -> str | None:
    taught = fold.taught_ids(view.subject)
    for module in view.plan.modules:
        if module.status not in OPEN or not unlocked(view, module, fold):
            continue
        for cid, card in view.module_cards(module.id):
            flagged = fold.card(view.subject, cid).flagged(card.rev)
            fresh = cid not in taught and cid != skip
            if fresh and not flagged and _open(view, card, fold):
                return cid
    return None


def _to_review(view: View, fold: Fold) -> Module | None:
    """The first ``ready`` module fully taught but not yet reviewed."""
    taught = fold.taught_ids(view.subject)
    for module in view.plan.modules:
        cards = counted(view, module.id, fold)
        done = bool(cards) and all(cid in taught for cid, _ in cards)
        if (
            module.status == "ready"
            and done
            and not module_reviewed(view, module.id, fold)
        ):
            return module
    return None


def _no_card(view: View, fold: Fold, now_ms: int) -> RequestError:
    """``no_card_left`` with the subject's title and its next step."""
    states = [
        s.fsrs_state() for m in view.plan.modules for _, s in counted(view, m.id, fold)
    ]
    dues = [state["due"] for state in states if state is not None]
    return no_card_left(
        view.title,
        module=_to_review(view, fold),
        due_at=min(dues) if dues else None,
        writing=any(m.status == "generating" for m in view.plan.modules),
        now_ms=now_ms,
    )


def pick(
    view: View, fold: Fold, card_id: str | None, now_ms: int, skip: str = ""
) -> str:
    """The card a session teaches: ``card_id`` if open, else the next one.

    ``skip`` (no ``card_id``): never that card (Next card leaves it).

    Raises ``unknown_card``, ``locked``, ``no_card_left`` or, when it would
    teach an untaught card with 10 new cards already taught today,
    ``daily_new_cap``. Re-teaching a taught card is free.
    """
    if card_id:
        card = view.cards.get(card_id)
        if card is None:
            msg = f"unknown card {card_id!r} in {view.subject}"
            raise RequestError(UNKNOWN_CARD, msg)
        module = view.plan.module(card.module)
        ready = module is not None and module.status in OPEN
        if not (ready and module and unlocked(view, module, fold)) or not _open(
            view, card, fold
        ):
            msg = f"{card_id} is locked: its module or required cards are not done"
            raise RequestError(LOCKED, msg)
        chosen = card_id
    else:
        found = _first(view, fold, skip)
        if found is None:
            raise _no_card(view, fold, now_ms)
        chosen = found
    is_new = not fold.card(view.subject, chosen).taught
    if is_new and new_today(fold, now_ms) >= NEW_CAP:
        msg = f"{NEW_CAP} new cards today already; reviews still work"
        raise RequestError(DAILY_NEW_CAP, msg)
    return chosen
