# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Just-in-time cards for a module that unlocked (status ``generating``).

Sources: a pinned subject (URLs in the goal, ``webpages``) uses only those
pages, the model keeping the ones that fit the module. Otherwise the model
names canonical Wikipedia articles, code looks them up
and searches for more (``wiki.candidates``), drops loosely matching hits and
ranks the rest (``relevance``), and the model keeps only the on-topic pages
(``judge.pick_sources``) BEFORE drafting. The model (no tools) drafts cards
from those texts; a card is kept only if it passes the deck's rules
(``card_rules``), the verbatim excerpt check, the seven card rules (``vet``:
code checks, a judge, up to three repairs) and the per-card relevance gate
(``judge.gate``). A new module is written by the draft tier (``tiers``), a
requested regeneration (``Module.repeat``) by the repeat tier. No card
kept, fewer than 2 on-topic sources, or a model failure: the module is
``failed`` with the reason (``plan_approve`` on the same rev retries it) --
unless it already has cards (a regeneration, ``regen``), then it stays
``ready``. There is no minimum: one good card makes a module. Else
``ready``; a module drafted ahead (``pregenerated``, ``pregen``) goes back
to ``locked`` until it unlocks.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Final

from tutor import codes
from tutor.curriculum import (
    judge,
    plan_context,
    relevance,
    rules,
    vet,
    webpages,
    wiki,
)
from tutor.curriculum.draft_prompt import CARDS_SCHEMA, SYSTEM, prompt
from tutor.curriculum.errors import RequestError
from tutor.curriculum.plan_context import Scope
from tutor.curriculum.subject_store import LOCK, Change

_logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from tutor.curriculum.context import Context
    from tutor.curriculum.records import CardRec, Module

MAX_CARDS: Final = 12
MIN_SOURCES: Final = 2


def _settle(
    module: Module, existing: dict[str, CardRec], kept: dict[str, CardRec]
) -> dict[str, CardRec]:
    """Order after the module's last card; ``requires`` only on earlier live ones."""
    live = {cid for cid, c in existing.items() if not c.suspended}
    order = max(
        (c.order for c in existing.values() if c.module == module.id), default=0
    )
    for cid, rec in kept.items():
        order += 1
        rec.order = order
        rec.requires = [r for r in rec.requires if r in live]
        live.add(cid)
    return kept


def _pinned(ctx: Context, scope: Scope, urls: list[str]) -> list[wiki.Source] | str:
    """A pinned subject's sources: the learner's pages that fit the module."""
    try:
        pages = webpages.fetch(ctx.text, urls)
    except RequestError as err:
        _logger.warning("pinned page fetch failed: %s", err.message)
        return err.message
    chosen = judge.pick_sources(ctx, scope, pages, wiki.MAX_SOURCES)
    if not chosen:
        return f"none of the {len(pages)} pinned page(s) covers this module"
    return [webpages.source(p) for p in chosen]


def sources(ctx: Context, scope: Scope) -> list[wiki.Source] | str:
    """The on-topic sources (seeded for the excerpt check), or why none."""
    meta, module = scope.meta, scope.module
    urls = webpages.pinned(meta.goal)
    if urls:  # the learner named the pages: no wiki search, one page may do
        return _pinned(ctx, scope, urls)
    titles = judge.propose_titles(ctx, scope)
    try:
        pages = wiki.candidates(
            ctx.fetch, [module.title, *titles], [module.title, relevance.query(module)]
        )
    except (OSError, ValueError) as err:
        _logger.warning("source search failed: %r", err)
        return f"source search failed: {err}"
    ranked = relevance.shortlist(pages, relevance.focus(meta, module))
    chosen = judge.pick_sources(ctx, scope, ranked, wiki.MAX_SOURCES)
    if len(chosen) < MIN_SOURCES:
        have = f"{len(chosen)} on-topic source(s) of {len(pages)}"
        return f"found {have}, need {MIN_SOURCES}"
    return [wiki.seed(p) for p in chosen]


def _outcome(
    ctx: Context, subject: str, module: Module
) -> tuple[dict[str, CardRec], str | None, str | None]:
    """Draft and check the cards: (kept cards, error, its ``error_kind``)."""
    # Every call sees the other modules, so each card lands in the right one.
    scope = Scope(ctx.subjects.need_meta(subject), module, ctx.subjects.plan(subject))
    existing = ctx.subjects.cards(subject)
    try:
        found = sources(ctx, scope)
        if isinstance(found, str):  # the search failed or found too few
            return {}, found, codes.SOURCES_MISSING
        raw = ctx.model(SYSTEM, prompt(scope, existing, found), CARDS_SCHEMA)
        items = raw.get("cards")
        batch = vet.Batch(scope, found, frozenset(existing), limit=MAX_CARDS)
        vetted = vet.vet(ctx, batch, items if isinstance(items, list) else [])
        known = plan_context.in_deck(scope.plan, module, existing, set())
        kept, refused = judge.gate(
            ctx, scope, vetted.kept, {s.url: s.title for s in found}, known
        )
        problems = vetted.dropped + refused
    except RequestError as err:
        _logger.warning("card drafting failed: %s", err.message)
        return {}, err.message, codes.error_kind(err)
    if not kept:
        return {}, _no_card(problems), codes.TOO_FEW_CARDS
    return _settle(module, existing, kept), None, None


def _no_card(problems: list[str]) -> str:
    """Why a module failed with no card passing (the first problems)."""
    shown = f" ({'; '.join(problems[:3])})" if problems else ""
    return f"no card passed the checks{shown}"


def _live(cards: dict[str, CardRec], module_id: str) -> int:
    return sum(c.module == module_id and not c.suspended for c in cards.values())


def generate(ctx: Context, subject: str, module_id: str) -> dict[str, Any]:
    """Generate one ``generating`` module's cards; returns its new status."""
    plan = ctx.subjects.plan(subject)
    module = plan.module(module_id) if plan else None
    if module is None or module.status != "generating":
        return {"module": module_id, "status": module.status if module else None}
    # A new module is written by the draft tier; a requested regeneration
    # (``regen``) is a repeatable action and stays on the repeat tier.
    drafter = ctx if module.repeat else ctx.drafting()
    kept, error, kind = _outcome(drafter, subject, module)
    with LOCK:  # re-read: the fold may have changed other modules meanwhile
        meta = ctx.subjects.need_meta(subject)
        plan = ctx.subjects.plan(subject)
        current = plan.module(module_id) if plan else None
        if plan is None or current is None or current.status != "generating":
            return {"module": module_id, "status": None}
        cards = {**ctx.subjects.cards(subject), **kept}
        count = _live(cards, module_id)
        current.status = "failed" if error and not count else "ready"
        if current.status == "ready" and current.pregenerated:
            view = rules.View(subject, plan, cards)
            if rules.unlocked(view, current, ctx.fold()):
                current.pregenerated = False  # its requires were mastered meanwhile
            else:
                current.status = "locked"  # drafted ahead: study waits for requires
        # Only a failed module carries its error; a ready one served by its
        # existing cards reports the reason in the returned result only.
        failed = current.status == "failed"
        current.error = error if failed else None
        current.error_kind = kind if failed else None
        current.cards = count
        current.repeat = current.repeat and failed  # a retry stays on its tier
        ctx.subjects.commit(subject, meta, Change(plan=plan, cards=cards))
    return {
        "module": module_id,
        "status": current.status,
        "cards": current.cards,
        "error": error,
        "error_kind": kind,
    }
