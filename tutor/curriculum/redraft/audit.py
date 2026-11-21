# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""A redraft's final audit: a second, separate judge pass over the whole set.

Every card that survived drafting was judged once, in its batch
(``vet``). Here the finished module is judged again as a whole, with its
own prompt (``quality_judge.AUDIT_SYSTEM``, so it is a new call, not a
replay), together with the code checks and with the cards that replace a
*hard* old card marked hard (they need a memory aid). A card that fails is
sent through ``vet`` once more (repair, judge) and audited again; one that
fails the second audit is dropped. So every published card passed an audit
call. ``counts`` keeps what the first pass found, for the report.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

from tutor.curriculum import quality, quality_judge, vet

if TYPE_CHECKING:
    from tutor.curriculum.context import Context
    from tutor.curriculum.quality import Problem
    from tutor.curriculum.records import CardRec

ROUNDS: Final = 2


@dataclass
class Audited:
    """The cards that passed, why the rest were dropped, and the counts."""

    kept: dict[str, CardRec]
    dropped: list[str] = field(default_factory=list)
    counts: dict[str, Any] = field(default_factory=dict)


def _broken(
    ctx: Context, batch: vet.Batch, cards: dict[str, CardRec], hard: set[str]
) -> dict[str, list[Problem]]:
    """Card id -> what the audit judge or the code checks found ([]: clean)."""
    said = quality_judge.judge(
        ctx, batch.scope.about(), cards, hard, quality_judge.AUDIT_SYSTEM
    )
    return {
        cid: said[cid]
        + quality.problems(rec.front, rec.back, rec.mnemonic, hard=cid in hard)
        for cid, rec in cards.items()
    }


def _repaired(
    ctx: Context,
    batch: vet.Batch,
    kept: dict[str, CardRec],
    failing: dict[str, list[Problem]],
    hard: set[str],
) -> dict[str, CardRec]:
    """The failing cards after one more ``vet`` (only those that passed it)."""
    items: list[object] = [vet.as_item(cid, kept[cid], batch.found) for cid in failing]
    taken = frozenset({*batch.taken, *(c for c in kept if c not in failing)})
    again = vet.Batch(batch.scope, batch.found, taken, frozenset(hard), len(items))
    done = vet.vet(ctx, again, items)
    return {cid: done.kept[cid] for cid in failing if cid in done.kept}


def run(
    ctx: Context, batch: vet.Batch, cards: dict[str, CardRec], hard: set[str]
) -> Audited:
    """Audit ``cards`` (draft id -> card); ``hard``: ids that need a mnemonic."""
    out = Audited(dict(cards))
    pending = set(cards)
    first: list[list[Problem]] = []
    attempt = 0
    while pending:
        found = _broken(
            ctx, batch, {c: out.kept[c] for c in out.kept if c in pending}, hard
        )
        failing = {cid: why for cid, why in found.items() if why}
        if attempt == 0:
            first = list(found.values())
        attempt += 1
        fixed = (
            _repaired(ctx, batch, out.kept, failing, hard)
            if failing and attempt < ROUNDS
            else {}
        )
        for cid, why in failing.items():
            if cid in fixed:
                out.kept[cid] = fixed[cid]
            else:
                del out.kept[cid]
                out.dropped.append(f"{cid}: failed the audit ({quality.describe(why)})")
        pending = set(fixed)  # a repaired card is audited once more
    out.counts = {
        "cards": len(out.kept),
        "first_pass": quality.counts(first),
        "published": quality.counts([[] for _ in out.kept]),
    }
    return out
