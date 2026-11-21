# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Swap one built unit into its subject, atomically (one lock, one commit).

- A new card matched to an old one takes the old card's id with ``rev`` + 1:
  its taught state and review schedule key on the id, so they carry over
  unchanged, and the rev bump clears its flags.
- An old card with no match is suspended, never deleted (``tutor.redraft``
  holds when): it leaves the review queue, its history stays on disk.
- A unit of several pieces becomes several modules (``pieces.py``).
- A unit with no card, or whose module changed since the snapshot, changes
  nothing (``RequestError``): the old cards stay live.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final, NamedTuple

from tutor.cards import CardError
from tutor.curriculum import card_rules, paths, rules
from tutor.curriculum.errors import BAD_REQUEST, RequestError
from tutor.curriculum.ids import slug
from tutor.curriculum.redraft import pieces
from tutor.curriculum.subject_store import LOCK, Change

if TYPE_CHECKING:
    from collections.abc import Callable

    from tutor.curriculum.context import Context
    from tutor.curriculum.records import CardRec, Module, Plan
    from tutor.curriculum.redraft.run import Before
    from tutor.curriculum.redraft.unit import Result

MARK: Final = "redraft"  # ``CardRec.tutor`` key of a card the redraft suspended


def _refuse(message: str) -> RequestError:
    return RequestError(BAD_REQUEST, message)


def _same(snap: Before, live: dict[str, CardRec], module_id: str) -> bool:
    """Whether the module's live cards are still the snapshot's (ids, revs)."""
    now = {
        cid: c.rev
        for cid, c in live.items()
        if c.module == module_id and not c.suspended
    }
    return now == {cid: c.rev for cid, c in snap.live(module_id).items()}


class _Stage(NamedTuple):
    """Where a unit's cards land: the plan, its new modules and the time."""

    plan: Plan
    made: list[Module]
    now: int


def _ids(result: Result, live: dict[str, CardRec]) -> dict[str, str]:
    """Draft id -> final id: the matched old card's id, else a free slug."""
    final: dict[str, str] = {}
    for draft_id in result.cards:
        matched = result.match.get(draft_id)
        final[draft_id] = matched or slug(draft_id, {*live, *final.values()})
    return final


def _earlier(
    rec: CardRec, final: dict[str, str], seen: set[str], opens: Callable[[str], bool]
) -> list[str]:
    """``rec``'s requirements that are taught before it (final ids, once each).

    One of this unit staged before it (``seen``), or a card of an earlier
    module (``opens``). Anything else could never open.
    """
    needs = dict.fromkeys(final.get(r, r) for r in rec.requires)
    return [r for r in needs if r in seen or opens(r)]


def _placed(made: list[Module], result: Result) -> list[tuple[str, int, str]]:
    """``(module id, order, draft id)`` for every new card, in teaching order."""
    return [
        (module.id, order, draft_id)
        for module, piece in zip(made, result.pieces, strict=True)
        for order, draft_id in enumerate(piece["cards"], 1)
    ]


def _cards(
    result: Result, snap: Before, live: dict[str, CardRec], stage: _Stage
) -> dict[str, str]:
    """Stage the new cards into ``live``; returns draft id -> final id."""
    fresh = result.recs()
    final = _ids(result, live)
    for cid in snap.live(result.module):
        if cid not in result.match.values():
            live[cid].suspended = True
            live[cid].tutor = {**live[cid].tutor, MARK: stage.now}
    rank = {m.id: n for n, m in enumerate(stage.plan.modules)}

    def opens(cid: str) -> bool:
        """Whether ``cid`` is a live card of a module before this unit's."""
        return (
            cid in live
            and rank.get(live[cid].module, len(rank)) < rank[stage.made[0].id]
        )

    seen: set[str] = set()  # this unit's cards staged so far (teaching order)
    for module_id, order, draft_id in _placed(stage.made, result):
        rec, cid = fresh[draft_id], final[draft_id]
        was = live.get(cid)
        rec.module, rec.order, rec.origin = module_id, order, "generated"
        rec.rev = was.rev + 1 if was else 1
        rec.created = was.created if was else stage.now
        rec.requires = _earlier(rec, final, seen, opens)
        live[cid] = rec
        seen.add(cid)
    _uncycle(live, set(final.values()))
    return final


def _waits_on(live: dict[str, CardRec], start: str, mine: set[str]) -> bool:
    """Whether ``start`` (transitively) requires one of ``mine``."""
    todo, done = [start], {start}
    while todo:
        for need in live[todo.pop()].requires:
            if need in mine:
                return True
            if need in live and need not in done:
                done.add(need)
                todo.append(need)
    return False


def _uncycle(live: dict[str, CardRec], mine: set[str]) -> None:
    """Drop a new card's requirement on an outside card that waits on the unit.

    An old card of an earlier module may require a card of this module (the
    automation deck has one); a new card requiring it back would be a cycle.
    """
    for cid in mine:
        rec = live[cid]
        rec.requires = [
            r for r in rec.requires if r in mine or not _waits_on(live, r, mine)
        ]


def _prune(live: dict[str, CardRec]) -> None:
    """No card may wait on a suspended one (it could never open)."""
    gone = {cid for cid, c in live.items() if c.suspended}
    for rec in live.values():
        if not rec.suspended:
            rec.requires = [r for r in rec.requires if r not in gone]


def _paths(
    result: Result, final: dict[str, str], live: dict[str, CardRec]
) -> dict[str, tuple[int, Any]]:
    """Final card id -> (its new rev, its interrogation path)."""
    return {
        final[d]: (live[final[d]].rev, path)
        for d, path in result.paths.items()
        if d in final
    }


def _staged(
    ctx: Context, snap: Before, result: Result
) -> tuple[list[Module], dict[str, str]]:
    """Stage and commit the unit (the caller holds ``LOCK``)."""
    subject, module_id = result.subject, result.module
    meta = ctx.subjects.need_meta(subject)
    plan = ctx.subjects.plan(subject)
    old = plan.module(module_id) if plan else None
    live = ctx.subjects.cards(subject)
    if plan is None or old is None or not _same(snap, live, module_id):
        msg = f"{subject}/{module_id} changed since the snapshot; start again"
        raise _refuse(msg)
    made = pieces.modules(plan, old, result)
    final = _cards(result, snap, live, _Stage(plan, made, ctx.clock()))
    _prune(live)
    pieces.statuses(made, result, final, snap.taught)
    try:
        card_rules.check_set(live, {m.id: m for m in plan.modules})
    except CardError as err:
        raise _refuse(str(err)) from err
    if meta.status == "completed" and not rules.completed(plan):
        meta.status = "active"  # a new card: the subject is not finished
    ctx.subjects.commit(subject, meta, Change(plan=plan, cards=live))
    paths.save(ctx, subject, _paths(result, final, live))
    return made, final


def apply(ctx: Context, snap: Before, result: Result) -> dict[str, object]:
    """Swap ``result`` into its subject; returns what happened.

    Raises ``RequestError`` (nothing written) when the unit has no card,
    the module changed since the snapshot or the staged subject is invalid.
    """
    if not result.cards:
        why = "; ".join(result.dropped[:3])
        msg = f"{result.subject}/{result.module}: no card passed ({why})"
        raise _refuse(msg)
    with LOCK:
        made, final = _staged(ctx, snap, result)
    matched = result.match.values()
    return {
        "modules": [m.id for m in made],
        "cards": len(final),
        "kept_ids": sorted(matched),
        "suspended": [c for c in snap.live(result.module) if c not in matched],
        "final": final,
    }
