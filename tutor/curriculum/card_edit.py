# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``card_edit``: fix or add one card, validated like the deck itself.

Fields, word limits, the module's id prefixes, ``requires`` (known, no
cycle), then the source fetch and the verbatim excerpt check. Any refusal is
``edit_refused`` with the reason; nothing is written. Success bumps the
card's ``rev`` (clearing its flags) and sets ``origin`` to ``edited``. Ids are
never renamed and a card never moves to another module. ``mnemonic``: absent
keeps the card's, "" clears it (an Editor that does not know the field never
wipes one); ``split_of`` is never taken from a request.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any

from tutor.cards import CardError
from tutor.curriculum import card_rules
from tutor.curriculum.errors import EDIT_REFUSED, RequestError
from tutor.curriculum.ids import slug, valid_id
from tutor.curriculum.records import CardRec, Module, Plan, bad, id_list
from tutor.curriculum.subject_store import LOCK, Change

if TYPE_CHECKING:
    from tutor.curriculum.context import Context

FIELDS = ("front", "back", "source", "excerpt")


def _refuse(message: str) -> RequestError:
    return RequestError(EDIT_REFUSED, message)


def _fields(body: dict[str, Any]) -> dict[str, str]:
    if not all(isinstance(body.get(k), str) for k in FIELDS):
        msg = f"{', '.join(FIELDS)} must all be strings"
        raise bad(msg)
    return {k: " ".join(str(body[k]).split()) for k in FIELDS}


def _mnemonic(body: dict[str, Any], rec: CardRec) -> None:
    """Set the requested memory aid on one line (none in the body: keep it)."""
    value = body.get("mnemonic")
    if value is not None and not isinstance(value, str):
        msg = "mnemonic must be a string"
        raise bad(msg)
    if value is not None:
        rec.mnemonic = " ".join(value.split())


def _new_id(module: Module, front: str, found: dict[str, CardRec]) -> str:
    """A new card's id: the slug of its front, with the module's prefix."""
    prefix = module.prefixes[0] if module.prefixes else ""
    return slug(prefix + front, found)


def _new(
    module: Module,
    found: dict[str, CardRec],
    fields: dict[str, str],
    requires: list[str],
    now: int,
) -> CardRec:
    """A new card, last in its module."""
    orders = [c.order for c in found.values() if c.module == module.id]
    return CardRec(
        module=module.id,
        order=max(orders, default=0) + 1,
        requires=requires,
        origin="edited",
        created=now,
        front=fields["front"],
        back=fields["back"],
        source=fields["source"],
        excerpt=fields["excerpt"],
    )


def _verify(ctx: Context, staged: dict[str, CardRec], plan: Plan, cid: str) -> None:
    """Deck rules over the whole subject, then ``cid``'s excerpt check."""
    try:
        card_rules.check_set(staged, {m.id: m for m in plan.modules})
    except CardError as err:
        raise _refuse(str(err)) from err
    reason = card_rules.source_problem(ctx, cid, staged[cid])
    if reason:
        msg = f"excerpt check failed for {staged[cid].source}: {reason}"
        raise _refuse(msg)


def card_edit(body: dict[str, Any], ctx: Context) -> dict[str, Any]:
    """Save one card; returns ``{"card": id, "rev": n}``."""
    subject, given = body.get("subject"), body.get("card")
    if not valid_id(subject) or not (given is None or valid_id(given)):
        msg = "subject and card must be ids (card may be null for a new one)"
        raise bad(msg)
    fields = _fields(body)
    requires = id_list(body.get("requires", []), "requires")
    with LOCK:
        meta = ctx.subjects.need_meta(str(subject))
        plan = ctx.subjects.plan(str(subject))
        module = plan.module(str(body.get("module", ""))) if plan else None
        if plan is None or module is None:
            msg = f"unknown module {body.get('module')!r}"
            raise _refuse(msg)
        found = ctx.subjects.cards(str(subject))
        old = found.get(str(given)) if given else None
        if old is not None and old.module != module.id:
            msg = f"{given} belongs to {old.module}; cards never move modules"
            raise _refuse(msg)
        if old is None:
            cid = str(given) if given else _new_id(module, fields["front"], found)
            rec = _new(module, found, fields, requires, ctx.clock())
            module.cards += 1
        else:
            cid = str(given)
            rec = replace(old, requires=requires, rev=old.rev + 1, origin="edited")
            rec.front, rec.back = fields["front"], fields["back"]
            rec.source, rec.excerpt = fields["source"], fields["excerpt"]
        _mnemonic(body, rec)
        staged = {**found, cid: rec}
        _verify(ctx, staged, plan, cid)
        ctx.subjects.commit(str(subject), meta, Change(plan=plan, cards=staged))
    return {"card": cid, "rev": rec.rev}
