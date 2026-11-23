# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Apply a post-mortem to the unit's own cards: add, edit (and un-teach), suspend.

No cap on any of them (kuhy, 2026-11-23). In this order, so replacements
count toward ``card_ops.MIN_LIVE`` before anything is suspended:

1. **Add** each new card on its own seeded source
   ``SOURCE_HOST/<unit>/<rev>/<hash of front>`` (the rework pattern: code
   built, so no judge call; the excerpt is quoted from the seeded line).
2. **Edit** a card: new front and back on a fresh seeded source; if it was
   taught, an ``untaught`` event through ``ctx.log``, so the module must be
   passed again. A rev bump alone un-teaches nothing.
3. **Suspend** with its reason (``card_ops.remove``; its 3-live-card floor
   still refuses, recorded).

A KEPT card (``run.kept_cards``) never reaches this module as an edit or a
suspension. Every refusal is recorded with its reason, never raised: one bad
card must not lose the rest. The new and un-taught cards make
``module_state``'s reconcile write the signed ``done: false`` row itself.
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import TYPE_CHECKING, Any, Final

from tutor import sources
from tutor.curriculum import card_ops
from tutor.curriculum.card_edit import card_edit
from tutor.curriculum.errors import RequestError
from tutor.curriculum.eventlog import worker_event
from tutor.store import Store

if TYPE_CHECKING:
    from tutor.curriculum.context import Context

_logger = logging.getLogger(__name__)
SOURCE_HOST: Final = "https://postmortem.leetcode-coach.invalid"
_BREAK: Final = re.compile(r"[.!?](?=\s)")  # quote's sentence break: one sentence


def _seeded(unit: str, rev: int, front: str, back: str) -> str:
    """A fresh source URL holding one line built from the card."""
    tag = hashlib.sha256(f"{front}\n{back}".encode()).hexdigest()[:8]
    url = f"{SOURCE_HOST}/{unit}/{rev}/{tag}"
    sources.seed_text(url, _BREAK.sub(";", f"Post-mortem of {unit}: {front} {back}"))
    return url


def _refuse(out: dict[str, Any], what: tuple[str, str], reason: str) -> None:
    """Record a refused ``(op, card)`` with its reason in the report."""
    op, card = what
    out["refused"].append({"op": op, "card": card, "reason": reason})


def _add(ctx: Context, found: dict[str, Any], rev: int, out: dict[str, Any]) -> None:
    unit, module = found["unit"], found["modules"][0]
    for new in found["new_cards"]:
        front, back = new["front"], new["back"]
        url = _seeded(unit, rev, front, back)
        text = (front, back, url, f"{front} {back}")
        draft = card_ops.Draft(
            module, *text, code_built=True, origin=f"postmortem:{unit}:{rev}"
        )
        try:
            cid, _ = card_ops.add(ctx, found["subject"], draft)
        except RequestError as err:
            _logger.warning("post-mortem: card %r not added: %s", front, err.message)
            _refuse(out, ("add", front), err.message)
            continue
        out["added"].append(cid)


def _edit_one(
    ctx: Context, subject: str, card: dict[str, Any], where: tuple[str, int]
) -> None:
    """Rewrite ``card`` on a fresh seeded source; ``where`` is (unit, rev)."""
    old = ctx.subjects.cards(subject)[card["id"]]
    front = " ".join(card["new_front"].split()) or old.front
    back = " ".join(card["new_back"].split()) or old.back
    url = _seeded(*where, front, back)
    excerpt = card_ops.quoted(ctx, url, (front, back), f"{front} {back}")
    body = {
        "subject": subject,
        "card": card["id"],
        "module": old.module,
        "front": front,
        "back": back,
        "source": url,
        "excerpt": excerpt,
        "requires": list(old.requires),
    }
    card_edit(body, ctx, judged=False)


def _edit(ctx: Context, found: dict[str, Any], rev: int, out: dict[str, Any]) -> None:
    subject = found["subject"]
    for card in [c for c in found["cards"] if c["change"] == "edit"]:
        try:
            _edit_one(ctx, subject, card, (found["unit"], rev))
        except (RequestError, KeyError) as err:
            reason = err.message if isinstance(err, RequestError) else "no such card"
            _logger.warning("post-mortem: %s not edited: %s", card["id"], reason)
            _refuse(out, ("edit", card["id"]), reason)
            continue
        out["edited"].append(card["id"])
        if card["id"] in ctx.fold().taught_ids(subject):
            event = worker_event(
                "untaught", (subject, card["id"]), dev=ctx.device, at=ctx.clock()
            )
            ctx.log.append([event])
            Store(ctx.data_dir).unfinish_card(card["id"])
            out["untaught"].append(card["id"])


def _suspend(ctx: Context, found: dict[str, Any], out: dict[str, Any]) -> None:
    for card in [c for c in found["cards"] if c["change"] == "suspend"]:
        try:
            card_ops.remove(ctx, found["subject"], card["id"])
        except RequestError as err:
            _logger.warning("post-mortem: %s kept live: %s", card["id"], err.message)
            _refuse(out, ("suspend", card["id"]), err.message)
            continue
        out["suspended"].append({"id": card["id"], "reason": card["finding"]})


def apply(ctx: Context, found: dict[str, Any], rev: int) -> dict[str, Any]:
    """Apply ``found`` (``run.analyse``) as revision ``rev``; what happened."""
    out: dict[str, Any] = {
        "added": [],
        "edited": [],
        "untaught": [],
        "suspended": [],
        "refused": [],
    }
    _add(ctx, found, rev, out)
    _edit(ctx, found, rev, out)
    _suspend(ctx, found, out)
    return out
