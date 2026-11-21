# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``card_edit``: fix or add one card, validated like the deck itself.

Fields, word limits, the module's id prefixes, ``requires`` (known, no
cycle), the seven card rules (``quality``: the code checks, then the judge
on the repeat tier), then the source fetch and the verbatim excerpt check.
Any refusal is ``edit_refused`` with the reason; nothing is written. Success bumps the
card's ``rev`` (clearing its flags) and sets ``origin`` to ``edited``. Ids are
never renamed and a card never moves to another module. ``mnemonic``: absent
keeps the card's, "" clears it (an Editor that does not know the field never
wipes one); ``code`` (a skeleton) likewise, its layout kept; a card over
the 2 KB budget is ``bad_request``; ``split_of`` is never taken from a request.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any

from tutor.cards import CardError
from tutor.curriculum import card_rules, quality, quality_judge
from tutor.curriculum.errors import EDIT_REFUSED, RequestError
from tutor.curriculum.ids import slug, valid_id
from tutor.curriculum.plan_context import Scope
from tutor.curriculum.records import CardRec, Module, Plan, bad, code, id_list
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


def new_id(module: Module, front: str, found: dict[str, CardRec]) -> str:
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


def _verified(
    ctx: Context, staged: dict[str, CardRec], plan: Plan, cid: str
) -> dict[str, CardRec]:
    """``staged`` once the deck rules and ``cid``'s excerpt check hold."""
    try:
        card_rules.check_set(staged, {m.id: m for m in plan.modules})
    except CardError as err:
        raise _refuse(str(err)) from err
    reason = card_rules.source_problem(ctx, cid, staged[cid])
    if reason:
        msg = f"excerpt check failed for {staged[cid].source}: {reason}"
        raise _refuse(msg)
    return staged


def _card_rules(ctx: Context, body: dict[str, Any], fields: dict[str, str]) -> None:
    """Refuse a card that breaks one of the seven rules (before any lock).

    Code checks first; only a card passing them costs a judge call.
    """
    subject = str(body.get("subject"))
    plan = ctx.subjects.plan(subject)
    module = plan.module(str(body.get("module", ""))) if plan else None
    if module is None:
        return  # an unknown module is refused below, with its own message
    old = ctx.subjects.cards(subject).get(str(body.get("card")))
    rec = CardRec(module.id, 0, fields["front"], fields["back"], "", "")
    rec.mnemonic = old.mnemonic if old else ""  # absent in the body: kept
    if isinstance(aid := body.get("mnemonic"), str):
        rec.mnemonic = aid
    broken = quality.problems(rec.front, rec.back, rec.mnemonic)
    if not broken:
        about = Scope(ctx.subjects.need_meta(subject), module, plan).about()
        broken = quality_judge.judge(ctx, about, {"card": rec}, set())["card"]
    if broken:
        msg = f"the card breaks a card rule ({quality.describe(broken)})"
        raise _refuse(msg)


def card_edit(
    body: dict[str, Any], ctx: Context, *, judged: bool = True
) -> dict[str, Any]:
    """Save one card; returns ``{"card": id, "rev": n}``.

    ``judged=False`` (never a client's choice: ``card_ops.Draft.code_built``)
    skips the seven card rules for a card code built from a fixed bank.
    """
    subject, given = body.get("subject"), body.get("card")
    if not valid_id(subject) or not (given is None or valid_id(given)):
        msg = "subject and card must be ids (card may be null for a new one)"
        raise bad(msg)
    fields = _fields(body)
    requires = id_list(body.get("requires", []), "requires")
    if judged:
        _card_rules(ctx, body, fields)
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
            cid = str(given) if given else new_id(module, fields["front"], found)
            rec = _new(module, found, fields, requires, ctx.clock())
            module.cards += 1
        else:
            cid = str(given)
            rec = replace(old, requires=requires, rev=old.rev + 1, origin="edited")
            rec.front, rec.back = fields["front"], fields["back"]
            rec.source, rec.excerpt = fields["source"], fields["excerpt"]
        _mnemonic(body, rec)
        if "code" in body:
            rec.code = code(body["code"])
        rec.to_json()  # over the budget: refused before anything is written
        ctx.subjects.commit(
            str(subject),
            meta,
            Change(plan=plan, cards=_verified(ctx, {**found, cid: rec}, plan, cid)),
        )
    return {"card": cid, "rev": rec.rev}
