# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Just-in-time cards for a module that unlocked (status ``generating``).

Sources: the model names canonical Wikipedia articles, code looks them up
and searches for more (``wiki.candidates``), drops loosely matching hits and
ranks the rest (``relevance``), and the model keeps only the on-topic pages
(``judge.pick_sources``) BEFORE drafting. The model (no tools) drafts cards
from those texts; a card is kept only if it passes the deck's rules
(``card_rules``), the verbatim excerpt check and the per-card relevance gate
(``judge.gate``). Fewer than 3 kept, fewer than 2 on-topic sources, or a
model failure: the module is ``failed`` with the reason (``plan_approve`` on
the same rev retries it) -- unless it already has cards (a regeneration,
``regen``), then it stays ``ready``. Else ``ready``.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Final

from tutor.cards import CardError
from tutor.curriculum import card_rules, judge, relevance, wiki
from tutor.curriculum.draft_prompt import CARDS_SCHEMA, SYSTEM, prompt
from tutor.curriculum.errors import RequestError
from tutor.curriculum.ids import slug
from tutor.curriculum.plan_context import Scope
from tutor.curriculum.records import CardRec, Module
from tutor.curriculum.subject_store import LOCK, Change

_logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from tutor.curriculum.context import Context

MIN_CARDS: Final = 3
MAX_CARDS: Final = 12
MIN_SOURCES: Final = 2


def _one(
    ctx: Context,
    module: Module,
    taken: set[str],
    found: list[wiki.Source],
    item: object,
) -> tuple[str, CardRec] | str:
    """One drafted card checked: ``(id, card)``, or why it was refused."""
    if not isinstance(item, dict):
        return "not an object"
    index = item.get("source")
    if not isinstance(index, int) or not 1 <= index <= len(found):
        return f"{item.get('id')}: no such source"
    prefix = module.prefixes[0] if module.prefixes else ""
    base = slug(str(item.get("id") or item.get("front") or ""), fallback="card")
    cid = slug(base if base.startswith(prefix) else prefix + base, taken)
    needs = item.get("requires")
    rec = CardRec(
        module=module.id,
        order=0,
        front=str(item.get("front", "")).strip(),
        back=str(item.get("back", "")).strip(),
        source=found[index - 1].url,
        excerpt=" ".join(str(item.get("excerpt", "")).split()),
        requires=[str(r) for r in needs] if isinstance(needs, list) else [],
        created=ctx.clock(),
    )
    try:
        card_rules.as_card(cid, rec, module)
    except CardError as err:
        _logger.warning("drafted card refused: %s", err)
        return str(err)
    reason = card_rules.source_problem(ctx, cid, rec)
    return f"{cid}: {reason}" if reason else (cid, rec)


def _drafts(
    ctx: Context,
    module: Module,
    existing: dict[str, CardRec],
    found: list[wiki.Source],
    raw: dict[str, Any],
) -> tuple[dict[str, CardRec], list[str]]:
    """Check the model's cards in order; returns (kept, why others were not)."""
    kept: dict[str, CardRec] = {}
    problems: list[str] = []
    items = raw.get("cards")
    for item in (items if isinstance(items, list) else [])[:MAX_CARDS]:
        checked = _one(ctx, module, {*existing, *kept}, found, item)
        if isinstance(checked, str):
            problems.append(checked)
            continue
        kept[checked[0]] = checked[1]
    return kept, problems


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


def _sources(ctx: Context, scope: Scope) -> list[wiki.Source] | str:
    """The on-topic sources (seeded for the excerpt check), or why none."""
    meta, module = scope.meta, scope.module
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
) -> tuple[dict[str, CardRec], str | None]:
    """Draft and check the cards: (kept cards, error or None)."""
    # Every call sees the other modules, so each card lands in the right one.
    scope = Scope(ctx.subjects.need_meta(subject), module, ctx.subjects.plan(subject))
    existing = ctx.subjects.cards(subject)
    try:
        found = _sources(ctx, scope)
        if isinstance(found, str):
            return {}, found
        raw = ctx.model(SYSTEM, prompt(scope, existing, found), CARDS_SCHEMA)
        checked, problems = _drafts(ctx, module, existing, found, raw)
        named = {s.url: s.title for s in found}
        kept, refused = judge.gate(ctx, scope, checked, named)
        problems += refused
    except RequestError as err:
        _logger.warning("card drafting failed: %s", err.message)
        return {}, err.message
    if len(kept) < MIN_CARDS:
        shown = f" ({'; '.join(problems[:3])})" if problems else ""
        return {}, f"only {len(kept)} card(s) passed the checks{shown}"
    return _settle(module, existing, kept), None


def _live(cards: dict[str, CardRec], module_id: str) -> int:
    return sum(c.module == module_id and not c.suspended for c in cards.values())


def generate(ctx: Context, subject: str, module_id: str) -> dict[str, Any]:
    """Generate one ``generating`` module's cards; returns its new status."""
    plan = ctx.subjects.plan(subject)
    module = plan.module(module_id) if plan else None
    if module is None or module.status != "generating":
        return {"module": module_id, "status": module.status if module else None}
    kept, error = _outcome(ctx, subject, module)
    with LOCK:  # re-read: the fold may have changed other modules meanwhile
        meta = ctx.subjects.need_meta(subject)
        plan = ctx.subjects.plan(subject)
        current = plan.module(module_id) if plan else None
        if plan is None or current is None or current.status != "generating":
            return {"module": module_id, "status": None}
        cards = {**ctx.subjects.cards(subject), **kept}
        count = _live(cards, module_id)
        current.status = "failed" if error and count < MIN_CARDS else "ready"
        current.error, current.cards = error, count
        ctx.subjects.commit(subject, meta, Change(plan=plan, cards=cards))
    return {
        "module": module_id,
        "status": current.status,
        "cards": current.cards,
        "error": error,
    }
