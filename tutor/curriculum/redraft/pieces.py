# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""A redrafted unit's pieces as plan modules, and each piece's status.

- A unit of several pieces becomes several modules: the first keeps the
  module's id, the others get new ids right after it, each requires the one
  before, and every module that required the old one requires the last.
- A piece holding a card the learner was never taught is not ``mastered``
  (the ordinary unlock rule then holds back later modules' new cards); a
  later piece with no taught card waits ``locked`` + ``pregenerated``.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Final

from tutor.curriculum.ids import slug

if TYPE_CHECKING:
    from tutor.curriculum.records import Module, Plan
    from tutor.curriculum.redraft.unit import Result

_OPEN: Final = frozenset({"ready", "mastered"})


def modules(plan: Plan, old: Module, result: Result) -> list[Module]:
    """The piece modules, spliced into ``plan`` in place of ``old``."""
    taken = {m.id for m in plan.modules}
    made: list[Module] = []
    for n, piece in enumerate(result.pieces):
        first = n == 0
        mid = old.id if first else slug(piece["title"], taken, fallback=old.id)
        taken.add(mid)
        made.append(
            replace(
                old,
                id=mid,
                title=piece["title"] if len(result.pieces) > 1 else old.title,
                summary=piece["summary"] if len(result.pieces) > 1 else old.summary,
                requires=list(old.requires) if first else [made[-1].id],
                cards=len(piece["cards"]),
                error=None,
                error_kind=None,
                repeat=False,
            )
        )
    at = plan.modules.index(old)
    plan.modules[at : at + 1] = made
    for module in plan.modules[at + len(made) :]:  # dependents: the last piece
        module.requires = [
            made[-1].id if need == old.id else need for need in module.requires
        ]
    return made


def _status(old: Module, cards: list[str], taught: set[str], *, first: bool) -> None:
    """Set a piece's status in place (``old`` is the piece: a copy by now)."""
    if old.status not in _OPEN:
        return  # locked or failed: drafted ahead, as it was
    if all(cid in taught for cid in cards):
        old.status = old.status if first else "ready"  # ``advance`` re-masters it
    elif first or any(cid in taught for cid in cards):
        old.status = "ready"
    else:
        old.status, old.pregenerated = "locked", True


def statuses(
    made: list[Module], result: Result, final: dict[str, str], taught: set[str]
) -> None:
    """Set every piece's status from its cards' final ids."""
    for n, (module, piece) in enumerate(zip(made, result.pieces, strict=True)):
        _status(module, [final[d] for d in piece["cards"]], taught, first=n == 0)
