# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The ``split`` card edit: one card into 2-4 smaller ones (struggle contract §2).

Atomic: every child's excerpt is quoted by code from its page first (as for
``card_ops.add``; an empty ``source`` means the original's page), then, under
one lock, the children and the suspended original are staged, every deck rule
and every child's excerpt check run, and the subject is committed once. Any
refusal (``edit_refused``) leaves the subject untouched.

The children get NEW ids (``card_edit.new_id`` over every id the subject ever
had, suspended ones too), ``origin: edited``, ``split_of`` = the original, its
module and ``requires``, and the orders right after it (later cards move
down). Cards that required the original require every child instead, in its
place. The original is ``suspended`` (never deleted), marked ``{"split": ms,
"requires_of": {card: index}}`` so the Editor's ``card_restore`` reverts the
whole split in one step (``card_undo``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from tutor.cards import CardError
from tutor.curriculum import card_ops, card_rules
from tutor.curriculum.card_edit import new_id
from tutor.curriculum.errors import EDIT_REFUSED, RequestError
from tutor.curriculum.records import CardRec
from tutor.curriculum.subject_store import LOCK, Change

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tutor.curriculum.context import Context
    from tutor.curriculum.records import Module, Plan

MIN_PARTS: Final = 2
MAX_PARTS: Final = 4
SPLIT: Final = "split"  # the original's ``tutor`` mark


@dataclass(frozen=True)
class Part:
    """One child as the tutor drafts it (like an ``add``, in the original's module)."""

    front: str
    back: str
    source: str = ""  # "": the original's page
    quote: str = ""  # words the supporting sentence holds (``quote``)


def _refuse(message: str) -> RequestError:
    return RequestError(EDIT_REFUSED, message)


def _live(ctx: Context, subject: str, cid: str) -> CardRec:
    found = ctx.subjects.cards(subject).get(cid)
    if found is None:
        msg = f"unknown card {cid!r} in {subject}"
        raise _refuse(msg)
    if found.suspended:
        msg = f"{cid} is removed; only a live card can be split"
        raise _refuse(msg)
    return found


def _drafts(ctx: Context, old: CardRec, parts: Sequence[Part]) -> list[CardRec]:
    """The children, quoted from their pages (no id or order yet)."""
    if not MIN_PARTS <= len(parts) <= MAX_PARTS:
        msg = f"a split makes {MIN_PARTS}-{MAX_PARTS} cards, not {len(parts)}"
        raise _refuse(msg)
    out = []
    for part in parts:
        front, back = " ".join(part.front.split()), " ".join(part.back.split())
        if not front or not back:
            msg = "every card of a split needs a front and back"
            raise _refuse(msg)
        url = part.source.strip() or old.source
        excerpt = card_ops.quoted(ctx, url, (front, back), part.quote)
        out.append(CardRec(old.module, 0, front, back, url, excerpt))
    return out


def _stage(
    found: dict[str, CardRec], cid: str, module: Module, children: list[CardRec]
) -> list[str]:
    """Slot ``children`` in after ``cid`` in ``found``; returns their new ids."""
    old = found[cid]
    for rec in found.values():  # make room right after the original
        if rec.module == old.module and rec.order > old.order:
            rec.order += len(children)
    ids: list[str] = []
    for i, child in enumerate(children, 1):
        child.order, child.requires = old.order + i, list(old.requires)
        child.origin, child.split_of = "edited", cid
        ids.append(new_id(module, child.front, found))
        found[ids[-1]] = child
    was = {k: c.requires.index(cid) for k, c in found.items() if cid in c.requires}
    for other, at in was.items():
        found[other].requires[at : at + 1] = ids
    old.suspended = True
    old.tutor = {**old.tutor, "requires_of": was}
    return ids


def _verify(
    ctx: Context, found: dict[str, CardRec], plan: Plan, ids: list[str]
) -> None:
    """Every deck rule over the staged subject, then each child's excerpt check."""
    try:
        card_rules.check_set(found, {m.id: m for m in plan.modules})
    except CardError as err:
        raise _refuse(str(err)) from err
    for child_id in ids:
        reason = card_rules.source_problem(ctx, child_id, found[child_id])
        if reason:
            msg = f"excerpt check failed for {found[child_id].source}: {reason}"
            raise _refuse(msg)


def split(
    ctx: Context, subject: str, cid: str, parts: Sequence[Part]
) -> tuple[CardRec, list[str]]:
    """Split ``cid`` into ``parts``; returns the suspended original and the new ids."""
    children = _drafts(ctx, _live(ctx, subject, cid), parts)
    with LOCK:
        meta, plan = ctx.subjects.need_meta(subject), card_ops.need_plan(ctx, subject)
        found = ctx.subjects.cards(subject)
        # A card's module is always in the plan (``check_set`` holds it so).
        module = {m.id: m for m in plan.modules}[_live(ctx, subject, cid).module]
        for child in children:
            child.created = ctx.clock()
        ids = _stage(found, cid, module, children)
        found[cid].tutor[SPLIT] = ctx.clock()
        _verify(ctx, found, plan, ids)
        module.cards = sum(
            c.module == module.id and not c.suspended for c in found.values()
        )
        ctx.subjects.commit(subject, meta, Change(plan=plan, cards=found))
    return found[cid], ids
