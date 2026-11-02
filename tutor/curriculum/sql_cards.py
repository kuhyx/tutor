# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""FSRS cards for the guided SQL lessons: seeded when a concept is mastered.

``seed_concept`` turns a concept's cards from :mod:`sql_bank` into reviewable
cards of the MySQL subject: the real result in each back comes from the
engine (``Runner``), the excerpt is checked against its source like any other
card, and every new card is ``taught`` by the worker (so it is in the review
queue). Idempotent: a card id that exists is kept, a card already taught is
never taught again (that would reset its FSRS state), a suspended one stays
suspended. A failing card is skipped (and reported), never fatal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import TYPE_CHECKING, Final

from tutor.cards import CardError
from tutor.curriculum import card_rules
from tutor.curriculum.eventlog import worker_event
from tutor.curriculum.records import CardRec, Module
from tutor.curriculum.sql_bank import BANK
from tutor.curriculum.sql_card_spec import CardSpec, Outcome, back_text
from tutor.curriculum.subject_store import LOCK, Change

if TYPE_CHECKING:
    from collections.abc import Callable

    from tutor.curriculum.context import Context

SUBJECT: Final = "mysql-8-for-timed-sql-coding-tests-joins-and"
MODULE: Final = "sql-lessons"
TITLE: Final = "SQL lessons"
SUMMARY: Final = "Rules and traps from the guided SQL lessons, as prediction cards."
_logger = logging.getLogger(__name__)
__all__ = ["MODULE", "SUBJECT", "Change", "Seeded", "seed_all", "seed_concept"]


@dataclass
class Seeded:
    """What one seeding did: new card ids, cards taught, and key -> why skipped."""

    added: list[str] = field(default_factory=list)
    taught: list[str] = field(default_factory=list)
    skipped: dict[str, str] = field(default_factory=dict)

    def merge(self, other: Seeded) -> None:
        """Fold ``other`` into this result."""
        self.added += other.added
        self.taught += other.taught
        self.skipped |= other.skipped


def _record(
    ctx: Context, spec: CardSpec, run: Callable[[str, str], Outcome]
) -> CardRec:
    """The card for ``spec``; the engine runs its query (``ValueError``: none)."""
    outcome = run(spec.schema, spec.query) if spec.query else None
    return CardRec(
        module=MODULE,
        order=0,
        front=" ".join(spec.front.split()),
        back=" ".join(back_text(spec, outcome).split()),
        source=spec.source,
        excerpt=spec.excerpt,
        origin="seed",
        created=ctx.clock(),
    )


def _ensure_module(plan_modules: list[Module]) -> Module:
    for mod in plan_modules:
        if mod.id == MODULE:
            return mod
    mod = Module(MODULE, TITLE, SUMMARY, [], status="ready")
    plan_modules.append(mod)
    return mod


def _prepare(
    ctx: Context,
    specs: list[CardSpec],
    run: Callable[[str, str], Outcome],
) -> tuple[dict[str, CardRec], dict[str, str]]:
    """Engine run + source check per spec, outside any lock (Docker, network).

    Returns ``(records by card id, key -> why skipped)``.
    """
    ready: dict[str, CardRec] = {}
    skipped: dict[str, str] = {}
    for spec in specs:
        try:
            rec = _record(ctx, spec, run)
            reason = card_rules.source_problem(ctx, spec.card_id, rec)
        except (ValueError, OSError, RuntimeError) as err:
            _logger.warning("sql card %s skipped: %r", spec.key, err)
            skipped[spec.key] = f"{type(err).__name__}: {err}"
            continue
        if reason:
            _logger.warning("sql card %s skipped: excerpt check: %s", spec.key, reason)
            skipped[spec.key] = f"excerpt check failed: {reason}"
        else:
            ready[spec.card_id] = rec
    return ready, skipped


def _commit(ctx: Context, subject: str, ready: dict[str, CardRec], out: Seeded) -> None:
    """Add ``ready`` to the subject in one short read-modify-write (under the lock)."""
    with LOCK:
        meta, plan = ctx.subjects.meta(subject), ctx.subjects.plan(subject)
        if meta is None or plan is None:
            return
        found = ctx.subjects.cards(subject)
        mod = _ensure_module(plan.modules)
        order = max((c.order for c in found.values() if c.module == MODULE), default=0)
        fresh = {cid: rec for cid, rec in ready.items() if cid not in found}
        for number, rec in enumerate(fresh.values(), start=order + 1):
            rec.order = number  # one added meanwhile is kept, not replaced
        found |= fresh
        if not fresh:
            return
        try:
            card_rules.check_set(found, {m.id: m for m in plan.modules})
        except CardError as err:
            _logger.warning("sql cards refused by the deck rules: %s", err)
            out.skipped["*"] = f"deck rules: {err}"
            return
        mod.cards = sum(c.module == MODULE and not c.suspended for c in found.values())
        ctx.subjects.commit(subject, meta, Change(plan=plan, cards=found))
        out.added += list(fresh)


def _add_cards(
    ctx: Context,
    subject: str,
    specs: tuple[CardSpec, ...],
    run: Callable[[str, str], Outcome],
) -> Seeded:
    """Write the missing cards of ``specs``; returns what happened.

    The slow part (engine, page fetch) runs first and unlocked; the commit
    re-reads the subject under the lock, so it is a short read-modify-write.
    """
    have = ctx.subjects.cards(subject)
    plan = ctx.subjects.plan(subject)
    if plan is None or plan.status != "approved":
        return Seeded()
    ready, skipped = _prepare(ctx, [s for s in specs if s.card_id not in have], run)
    out = Seeded(skipped=skipped)
    _commit(ctx, subject, ready, out)
    return out


def _teach(ctx: Context, subject: str, ids: list[str], at: int) -> list[str]:
    """``taught`` events (by the worker) for the live cards not taught yet."""
    cards = ctx.subjects.cards(subject)
    taught = ctx.fold().taught_ids(subject)
    todo = [i for i in ids if i in cards and not cards[i].suspended and i not in taught]
    ctx.log.append(
        worker_event("taught", (subject, i), dev=ctx.device, at=at) for i in todo
    )
    return todo


def seed_concept(
    ctx: Context,
    concept: str,
    run: Callable[[str, str], Outcome],
    *,
    subject: str = SUBJECT,
    taught_at: int | None = None,
) -> Seeded:
    """Cards of ``concept`` into ``subject``; taught at ``taught_at`` (default now).

    A concept the bank does not know, or a missing / unapproved subject, is a
    quiet no-op. Backdating ``taught_at`` makes the first review due earlier.
    """
    specs = BANK.get(concept, ())
    out = _add_cards(ctx, subject, specs, run) if specs else Seeded()
    if specs and ctx.subjects.plan(subject) is not None:
        at = ctx.clock() if taught_at is None else taught_at
        out.taught = _teach(ctx, subject, [s.card_id for s in specs], at)
    return out


def seed_all(
    ctx: Context,
    run: Callable[[str, str], Outcome],
    *,
    subject: str = SUBJECT,
    taught_at: int | None = None,
) -> Seeded:
    """Every concept of the bank (the backfill of lessons learned before this)."""
    out = Seeded()
    for concept in BANK:
        out.merge(seed_concept(ctx, concept, run, subject=subject, taught_at=taught_at))
    return out
