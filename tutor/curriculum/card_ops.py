# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The tutor's own card edits, applied to the data-dir subject (never the repo).

- :func:`rewrite`: new front and/or back, and optionally a new source (a
  page the tutor's research found): code quotes the new excerpt from it
  (``quote``), as for :func:`add`; ``requires`` stays. Through ``card_edit``,
  so every deck rule and the excerpt check (against the new URL) run.
- :func:`add`: a new card from front, back and a source URL. Code quotes the
  supporting sentence of the page (``quote``), then ``card_edit`` checks the
  card exactly as for any other edit.
- :func:`remove`: suspend (never delete) and drop the id from other cards'
  ``requires``; refused when the module would keep fewer than 3 live cards.
- :func:`mnemonic`: set or clear (``""``) the card's memory aid, through
  ``card_edit`` (rev + 1). Splits: ``card_split``.

Every refusal is ``edit_refused`` with the reason, and nothing is written.

The card's ``tutor`` mark ({} = none, left out of its JSON) records
``{"added": ms}`` and ``{"removed" | "editor_removed": ms, "requires_of":
{card: index}}`` (the Editor's Remove writes the latter).
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


def need_plan(ctx: Context, subject: str) -> Plan:
    """The subject's plan, or ``edit_refused`` when it has none."""
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


@dataclass(frozen=True)
class Rewrite:
    """A change to a card's text and/or source; an empty field keeps the old."""

    front: str = ""
    back: str = ""
    source: str = ""  # a new page: its excerpt is quoted by code
    quote: str = ""  # words the new page's supporting sentence holds


def rewrite(ctx: Context, subject: str, cid: str, change: Rewrite) -> CardRec:
    """``cid`` with ``change`` applied; returns the card.

    A ``source`` other than the card's moves it to that page: the excerpt is
    re-quoted from the page by code (``quote``: words of the supporting
    sentence), never taken from the model.
    """
    old = _card(ctx, subject, cid)
    new = (
        " ".join(change.front.split()) or old.front,
        " ".join(change.back.split()) or old.back,
    )
    url, excerpt = change.source.strip() or old.source, old.excerpt
    if new == (old.front, old.back) and url == old.source:
        msg = f"the edit of {cid} changes nothing"  # a rev bump clears flags
        raise _refuse(msg)
    if url != old.source:
        excerpt = quoted(ctx, url, new, change.quote)
    body = {
        "subject": subject,
        "card": cid,
        "module": old.module,
        "front": new[0],
        "back": new[1],
        "source": url,
        "excerpt": excerpt,
        "requires": list(old.requires),
    }
    card_edit(body, ctx)
    return _card(ctx, subject, cid)


def mnemonic(ctx: Context, subject: str, cid: str, text: str) -> CardRec:
    """``cid`` with its memory aid set to ``text`` ("" clears it); returns the card."""
    old = _card(ctx, subject, cid)
    aid = " ".join(text.split())
    if aid == old.mnemonic:
        msg = f"the mnemonic of {cid} is already that"  # a rev bump clears flags
        raise _refuse(msg)
    body = {
        "subject": subject,
        "card": cid,
        "module": old.module,
        "front": old.front,
        "back": old.back,
        "source": old.source,
        "excerpt": old.excerpt,
        "requires": list(old.requires),
        "mnemonic": aid,
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


def quoted(ctx: Context, url: str, card: tuple[str, str], hint: str) -> str:
    """The sentence of ``url`` that supports ``card`` (front, back), by code."""
    excerpt = quote.supporting(_page(ctx, url), card[1], card[0], hint)
    if excerpt is None:
        msg = f"no sentence of {url} supports that answer"
        raise _refuse(msg)
    return excerpt


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
    module = _module(need_plan(ctx, subject), draft.topic)
    source = draft.source.strip()
    excerpt = quoted(ctx, source, (draft.front, draft.back), draft.quote)
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

    Marked with where its id stood in other cards' ``requires`` so the
    Editor's Restore is exact (``card_undo``): ``removed`` when ``by_tutor``,
    else ``editor_removed`` (the Editor's own Remove).
    """
    with LOCK:
        meta = ctx.subjects.need_meta(subject)
        plan = need_plan(ctx, subject)
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
        mark = "removed" if by_tutor else "editor_removed"
        rec.tutor = {**rec.tutor, mark: ctx.clock(), "requires_of": was}
        for module in plan.modules:
            if module.id == rec.module:
                module.cards = live - 1
        ctx.subjects.commit(subject, meta, Change(plan=plan, cards=cards))
    return rec
