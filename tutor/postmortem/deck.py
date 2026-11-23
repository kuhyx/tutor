# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The planned path of a unit: its live cards, how they were taught and reviewed.

The planned path is the module's cards plus their interrogation paths
(``paths.json``). The card-side struggle signal is the review grades of the
fold: how many Again (1) ratings each card took since it was taught.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import TYPE_CHECKING, Any, Final

from tutor.curriculum import paths

if TYPE_CHECKING:
    from tutor.curriculum.context import Context

AGAIN: Final = 1
MAX_PATH: Final = 600  # characters of a card's interrogation path in the prompt


@dataclass(frozen=True)
class Card:
    """One live card of the unit."""

    id: str
    module: str
    front: str
    back: str
    taught: bool
    reviews: int
    again: int
    path: str

    def line(self) -> str:
        """The card as one prompt block."""
        state = "taught" if self.taught else "not taught"
        head = f"[{self.id}] ({self.module}, {state}, {self.reviews} reviews, "
        out = f"{head}{self.again} Again)\nQ: {self.front}\nA: {self.back}"
        return f"{out}\nPath: {self.path}" if self.path else out


def _path(found: object) -> str:
    text = json.dumps(found, ensure_ascii=False) if found else ""
    return text if len(text) <= MAX_PATH else text[:MAX_PATH] + " [...]"


def unit_cards(ctx: Context, subject: str, modules: tuple[str, ...]) -> list[Card]:
    """The live cards of ``modules``, in module then card order."""
    folded = ctx.fold().cards
    stored = paths.load(ctx, subject)
    cards = ctx.subjects.cards(subject)
    order = {m: i for i, m in enumerate(modules)}
    live = sorted(
        ((cid, c) for cid, c in cards.items() if c.module in order and not c.suspended),
        key=lambda item: (order[item[1].module], item[1].order, item[0]),
    )
    out = []
    for cid, rec in live:
        state = folded.get((subject, cid))
        ratings = [r for _, r in state.reviews] if state else []
        path = stored.get(cid, {})
        current = path.get("path") if path.get("rev") == rec.rev else None
        out.append(
            Card(
                cid,
                rec.module,
                rec.front,
                rec.back,
                bool(state and state.taught),
                len(ratings),
                sum(r == AGAIN for r in ratings),
                _path(current),
            )
        )
    return out


def module_text(ctx: Context, subject: str, modules: tuple[str, ...]) -> str:
    """The titles and summaries of ``modules``."""
    plan = ctx.subjects.plan(subject)
    found = [plan.module(m) for m in modules] if plan else []
    return "\n".join(f"- {m.id}: {m.title}. {m.summary}" for m in found if m)


def future_modules(
    ctx: Context, subject: str, modules: tuple[str, ...]
) -> list[dict[str, Any]]:
    """Every module after the unit's in the plan: id, title, summary, taught count."""
    plan = ctx.subjects.plan(subject)
    if plan is None:
        return []
    ids = [m.id for m in plan.modules]
    last = max((ids.index(m) for m in modules if m in ids), default=len(ids))
    taught = ctx.fold().taught_ids(subject)
    cards = ctx.subjects.cards(subject)
    out = []
    for module in plan.modules[last + 1 :]:
        mine = [
            c for c, r in cards.items() if r.module == module.id and not r.suspended
        ]
        out.append(
            {
                "module": module.id,
                "title": module.title,
                "summary": module.summary,
                "cards": len(mine),
                "taught": sum(c in taught for c in mine),
            }
        )
    return out
