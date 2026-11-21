# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Drafted cards in, rule-abiding cards out: check, judge, repair, drop.

Every drafted card goes through, in order: the deck's own rules and the
verbatim excerpt check (:func:`one`), the code checks of the seven card
rules (``quality.problems``) and the model judge (``quality_judge.judge``).
Cards that fail anything are handed back to the model with what is wrong
(``quality_judge.repair``) at most :data:`REPAIR_ROUNDS` times; a card that
still fails is dropped and reported, never published. A passing card is
never judged twice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import TYPE_CHECKING, Final

from tutor.cards import CardError
from tutor.curriculum import card_rules, quality, quality_judge
from tutor.curriculum.errors import RequestError
from tutor.curriculum.ids import slug
from tutor.curriculum.records import CardRec

if TYPE_CHECKING:
    from tutor.curriculum import wiki
    from tutor.curriculum.context import Context
    from tutor.curriculum.plan_context import Scope
    from tutor.curriculum.records import Module

REPAIR_ROUNDS: Final = 3
_logger = logging.getLogger(__name__)


@dataclass
class Vetted:
    """What a vetting kept (id -> card, in order) and why it dropped the rest."""

    kept: dict[str, CardRec] = field(default_factory=dict)
    dropped: list[str] = field(default_factory=list)
    rounds: int = 0  # repair calls made


@dataclass(frozen=True)
class Batch:
    """What one vetting runs against."""

    scope: Scope
    found: list[wiki.Source]
    taken: frozenset[str] = frozenset()  # ids no new card may take
    hard: frozenset[str] = frozenset()  # ids the learner found hard (rule g)
    limit: int = 12


def texts(found: list[wiki.Source]) -> str:
    """The numbered source texts, as every drafting and repair call sees them."""
    return "\n\n".join(
        f'<source n="{i}" url="{s.url}">\n{s.text}\n</source>'
        for i, s in enumerate(found, 1)
    )


def as_item(cid: str, rec: CardRec, found: list[wiki.Source]) -> dict[str, object]:
    """A stored card as a drafted item (its source by number; 0: not listed)."""
    urls = [s.url for s in found]
    return {
        "id": cid,
        "front": rec.front,
        "back": rec.back,
        "mnemonic": rec.mnemonic,
        "code": rec.code,
        "source": urls.index(rec.source) + 1 if rec.source in urls else 0,
        "excerpt": rec.excerpt,
        "requires": list(rec.requires),
    }


def one(
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
        return "no such source"
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
        mnemonic=" ".join(str(item.get("mnemonic") or "").split()),
        code=str(item.get("code") or "").rstrip(),  # a skeleton keeps its layout
    )
    try:
        card_rules.as_card(cid, rec, module)
        rec.to_json()  # over the card budget: refused here, not at commit
    except (CardError, RequestError) as err:
        _logger.warning("drafted card refused: %s", err)
        return str(err)
    reason = card_rules.source_problem(ctx, cid, rec)
    return reason or (cid, rec)


def _label(item: object, n: int) -> str:
    """What a refused item is called in a repair prompt and a report."""
    named = item.get("id") if isinstance(item, dict) else None
    return str(named) if named else f"card-{n}"


def _code(rec: CardRec, *, hard: bool) -> list[quality.Problem]:
    """What the code checks of the seven rules find in ``rec``."""
    return quality.problems(rec.front, rec.back, rec.mnemonic, hard=hard)


def _round(
    ctx: Context, batch: Batch, items: list[object], out: Vetted
) -> dict[str, tuple[object, str]]:
    """Check ``items``; passing cards go to ``out.kept``; returns the failing."""
    failing: dict[str, tuple[object, str]] = {}
    checked: dict[str, tuple[object, CardRec]] = {}
    for n, item in enumerate(items):
        used = {*batch.taken, *out.kept, *checked}
        got = one(ctx, batch.scope.module, used, batch.found, item)
        if isinstance(got, str):
            failing[_label(item, n)] = (item, got)
            continue
        cid, rec = got
        broken = _code(rec, hard=cid in batch.hard)
        if broken:
            failing[cid] = (item, quality.describe(broken))
        else:
            checked[cid] = (item, rec)
    cards = {cid: rec for cid, (_, rec) in checked.items()}
    said = quality_judge.judge(ctx, batch.scope.about(), cards, set(batch.hard))
    for cid, (item, rec) in checked.items():
        if said[cid]:
            failing[cid] = (item, quality.describe(said[cid]))
        else:
            out.kept[cid] = rec
    return failing


def vet(ctx: Context, batch: Batch, items: list[object]) -> Vetted:
    """Check ``items`` (drafted cards), repairing failures up to 3 times.

    A ``RequestError`` from the model propagates: nothing half-vetted is
    returned.
    """
    out = Vetted()
    pending = items[: batch.limit]
    while True:
        failing = _round(ctx, batch, pending, out)
        if not failing or out.rounds == REPAIR_ROUNDS:
            break
        out.rounds += 1
        room = max(batch.limit - len(out.kept), 0)
        pending = quality_judge.repair(
            ctx, batch.scope.about(), texts(batch.found), failing
        )[:room]
        fixed = {item["fixes"] for item in pending if isinstance(item, dict)}
        out.dropped += [  # the model left it out: an opinion, an unsupported fact
            f"{key}: {why}" for key, (_, why) in failing.items() if key not in fixed
        ]
    out.dropped += [f"{key}: {why}" for key, (_, why) in failing.items()]
    return out
