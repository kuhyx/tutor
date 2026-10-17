# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The tutor's own card edits, applied to the data-dir subject (never the repo).

- :func:`rewrite`: new front and/or back; source, excerpt and ``requires``
  stay. Through ``card_edit``, so every deck rule and the excerpt check run.
- :func:`add`: a new card from front, back and a source URL. Code quotes the
  supporting sentence of the page (``quote``), then ``card_edit`` checks the
  card exactly as for any other edit.
- :func:`remove`: suspend (never delete) and drop the id from other cards'
  ``requires``; refused when the module would keep fewer than 3 live cards.

Every refusal is ``edit_refused`` with the reason, and nothing is written.

The card's ``tutor`` mark ({} = none, left out of its JSON) records
``{"added": ms}`` and ``{"removed": ms, "requires_of": {card: index}}``.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any, Final
from urllib.parse import urlsplit

from tutor.curriculum import quote, wiki
from tutor.curriculum.card_edit import card_edit
from tutor.curriculum.errors import EDIT_REFUSED, RequestError
from tutor.curriculum.subject_store import LOCK, Change

if TYPE_CHECKING:
    from tutor.curriculum.context import Context
    from tutor.curriculum.records import CardRec, Module, Plan

MIN_LIVE: Final = 3
_logger = logging.getLogger(__name__)


def _refuse(message: str) -> RequestError:
    return RequestError(EDIT_REFUSED, message)


def _plan(ctx: Context, subject: str) -> Plan:
    plan = ctx.subjects.plan(subject)
    if plan is None:
        msg = f"{subject} has no plan"
        raise _refuse(msg)
    return plan


def _card(ctx: Context, subject: str, cid: str) -> CardRec:
    found = ctx.subjects.cards(subject).get(cid)
    if found is None:
        msg = f"unknown card {cid!r} in {subject}"
        raise _refuse(msg)
    return found


def rewrite(ctx: Context, subject: str, cid: str, *, front: str, back: str) -> CardRec:
    """``cid`` with a new front and/or back (empty: kept); returns the card."""
    old = _card(ctx, subject, cid)
    new = (" ".join(front.split()) or old.front, " ".join(back.split()) or old.back)
    if new == (old.front, old.back):  # a rev bump would clear the learner's flags
        msg = f"the edit of {cid} changes nothing"
        raise _refuse(msg)
    body = {
        "subject": subject,
        "card": cid,
        "module": old.module,
        "front": new[0],
        "back": new[1],
        "source": old.source,
        "excerpt": old.excerpt,
        "requires": list(old.requires),
    }
    card_edit(body, ctx)
    return _card(ctx, subject, cid)


def _module(plan: Plan, ref: str) -> Module:
    """The module named by id or title (case and spacing ignored)."""
    want = " ".join(ref.split()).casefold()
    for module in plan.modules:
        if want in {module.id, module.title.casefold()}:
            return module
    ids = ", ".join(m.id for m in plan.modules)
    msg = f"unknown topic {ref!r}; topics are: {ids}"
    raise _refuse(msg)


def _page(ctx: Context, url: str) -> str:
    """The page's plain text, as the excerpt check will read it."""
    if urlsplit(url).scheme != "https" or not urlsplit(url).hostname:
        msg = f"source must be an https URL, not {url!r}"
        raise _refuse(msg)
    try:  # a wiki page: seed the extract the check reads (as card_rules does)
        wiki.reseed(ctx.fetch, url)
    except (OSError, ValueError) as err:
        _logger.warning("could not seed %s: %r", url, err)
    try:
        return ctx.text(url)
    except (OSError, ValueError) as err:
        msg = f"cannot read {url}: {err}"
        raise _refuse(msg) from err


@dataclass(frozen=True)
class Draft:
    """A card the tutor proposes: ``topic`` is a module id or title."""

    topic: str
    front: str
    back: str
    source: str
    quote: str = ""  # words the supporting sentence holds (``quote``)


def add(ctx: Context, subject: str, draft: Draft) -> tuple[str, CardRec]:
    """A new card from ``draft``; returns its id and card."""
    module = _module(_plan(ctx, subject), draft.topic)
    source = draft.source.strip()
    page = _page(ctx, source)
    excerpt = quote.supporting(page, draft.back, draft.front, draft.quote)
    if excerpt is None:
        msg = f"no sentence of {source} supports that answer"
        raise _refuse(msg)
    body: dict[str, Any] = {
        "subject": subject,
        "card": None,
        "module": module.id,
        "front": draft.front,
        "back": draft.back,
        "source": source,
        "excerpt": excerpt,
        "requires": [],
    }
    cid = str(card_edit(body, ctx)["card"])
    with LOCK:  # the mark the Editor's Remove keys on
        meta, cards = ctx.subjects.need_meta(subject), ctx.subjects.cards(subject)
        cards[cid].tutor = {"added": ctx.clock()}
        ctx.subjects.commit(subject, meta, Change(cards=cards))
    return cid, cards[cid]


def remove(ctx: Context, subject: str, cid: str, *, by_tutor: bool = True) -> CardRec:
    """Suspend ``cid``; returns the suspended card.

    ``by_tutor``: marked ``removed`` with where its id stood in other cards'
    ``requires``, so the Editor's Restore is exact (``card_undo``).
    """
    with LOCK:
        meta = ctx.subjects.need_meta(subject)
        plan = _plan(ctx, subject)
        cards = ctx.subjects.cards(subject)
        rec = cards.get(cid)
        if rec is None:
            msg = f"unknown card {cid!r} in {subject}"
            raise _refuse(msg)
        if rec.suspended:
            msg = f"{cid} is already removed"
            raise _refuse(msg)
        live = sum(c.module == rec.module and not c.suspended for c in cards.values())
        if live - 1 < MIN_LIVE:
            msg = (
                f"removing {cid} would leave module {rec.module} with {live - 1} "
                f"live cards; it needs at least {MIN_LIVE} live cards"
            )
            raise _refuse(msg)
        rec.suspended = True
        was = {k: c.requires.index(cid) for k, c in cards.items() if cid in c.requires}
        for other in cards.values():  # no rev bump: a rev bump clears flags
            other.requires = [r for r in other.requires if r != cid]
        if by_tutor:
            rec.tutor = {**rec.tutor, "removed": ctx.clock(), "requires_of": was}
        for module in plan.modules:
            if module.id == rec.module:
                module.cards = live - 1
        ctx.subjects.commit(subject, meta, Change(plan=plan, cards=cards))
    return rec
