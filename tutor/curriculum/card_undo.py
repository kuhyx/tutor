# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The Editor's undo of the tutor's card edits (build lane, like ``card_edit``).

- ``card_restore``: a card the tutor removed comes back: un-suspended, and
  its id put back where it stood in the ``requires`` of the cards it was
  dropped from (recorded at removal, ``card_ops.remove``).
- ``card_remove``: a card the tutor added is suspended (never deleted), with
  ``card_ops.remove``'s rules: refused below 3 live cards in its module.

A tutor rewrite needs no undo of its own: the Editor edits the text back.
Refusals are ``edit_refused``; nothing is written then.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tutor.cards import CardError
from tutor.curriculum import card_ops, card_rules
from tutor.curriculum.errors import EDIT_REFUSED, RequestError
from tutor.curriculum.ids import valid_id
from tutor.curriculum.records import bad
from tutor.curriculum.subject_store import LOCK, Change

if TYPE_CHECKING:
    from tutor.curriculum.context import Context
    from tutor.curriculum.records import CardRec


def _ids(body: dict[str, Any]) -> tuple[str, str]:
    subject, cid = body.get("subject"), body.get("card")
    if not valid_id(subject) or not valid_id(cid):
        msg = "subject and card must be ids"
        raise bad(msg)
    return str(subject), str(cid)


def _refuse(message: str) -> RequestError:
    return RequestError(EDIT_REFUSED, message)


def restore(ctx: Context, subject: str, cid: str) -> CardRec:
    """Un-suspend a tutor-removed ``cid`` and put back its ``requires`` edges."""
    with LOCK:
        meta = ctx.subjects.need_meta(subject)
        plan = ctx.subjects.plan(subject)
        cards = ctx.subjects.cards(subject)
        rec = cards.get(cid)
        if plan is None or rec is None:
            msg = f"unknown card {cid!r} in {subject}"
            raise _refuse(msg)
        if not (rec.suspended and "removed" in rec.tutor):
            msg = f"{cid} was not removed by the tutor; nothing to restore"
            raise _refuse(msg)
        for other, at in dict(rec.tutor.get("requires_of") or {}).items():
            dep = cards.get(other)
            if dep is not None and cid not in dep.requires:
                dep.requires.insert(min(int(at), len(dep.requires)), cid)
        rec.suspended = False
        rec.tutor = {k: v for k, v in rec.tutor.items() if k == "added"}
        try:
            card_rules.check_set(cards, {m.id: m for m in plan.modules})
        except CardError as err:  # e.g. an Editor edit since made a cycle
            raise _refuse(str(err)) from err
        for module in plan.modules:
            if module.id == rec.module:
                module.cards = sum(
                    c.module == module.id and not c.suspended for c in cards.values()
                )
        ctx.subjects.commit(subject, meta, Change(plan=plan, cards=cards))
    return rec


def card_restore(body: dict[str, Any], ctx: Context) -> dict[str, Any]:
    """``card_restore``: ``{"subject","card"}`` -> ``{"card": id}``."""
    subject, cid = _ids(body)
    restore(ctx, subject, cid)
    return {"card": cid}


def card_remove(body: dict[str, Any], ctx: Context) -> dict[str, Any]:
    """``card_remove``: suspend a card the tutor added -> ``{"card": id}``."""
    subject, cid = _ids(body)
    found = ctx.subjects.cards(subject).get(cid)
    if found is not None and "added" not in found.tutor:
        msg = f"only a card the tutor added can be removed here, not {cid}"
        raise _refuse(msg)
    card_ops.remove(ctx, subject, cid, by_tutor=False)
    return {"card": cid}
