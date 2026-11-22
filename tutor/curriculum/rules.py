# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Unlock, mastery and recall; the gate and the pick are in ``pick``.

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

if TYPE_CHECKING:
    from tutor.curriculum.fold import CardFold, Fold
    from tutor.curriculum.records import CardRec, Module, Plan

GOOD_GAP_MS: Final = 20 * 3600 * 1000
GOOD_RATING: Final = 3
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
