# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Build one unit: a module's new cards, from the snapshot and the sources.

Pure with respect to the subject files (it reads ``before/`` only and
writes nothing): sources (``gather``), the draft, the seven card rules
(``vet``), the relevance gate (``judge.gate``), the match to the old cards,
the audit (``audit``: a separate judge pass over the whole final set, where
a card replacing a hard one must carry a memory aid; a card it fails is
repaired or dropped), the cut into pieces of at most 12 and each piece's
interrogation paths (``ctx.draft``). The
result is plain JSON (``out/<subject>/<module>.json``): ``swap`` applies it.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import logging
from typing import TYPE_CHECKING, Any

from tutor.curriculum import judge, paths, vet
from tutor.curriculum.draft_prompt import CARDS_SCHEMA
from tutor.curriculum.errors import MODEL_ERROR, RequestError
from tutor.curriculum.plan_context import Scope
from tutor.curriculum.records import CardRec
from tutor.curriculum.redraft import audit, gather, prompts

if TYPE_CHECKING:
    from tutor.curriculum import wiki
    from tutor.curriculum.context import Context
    from tutor.curriculum.redraft.run import Before

_logger = logging.getLogger(__name__)


@dataclass
class Result:
    """One built unit, as stored in ``out/``."""

    subject: str
    module: str
    cards: dict[str, dict[str, Any]] = field(default_factory=dict)  # draft id -> card
    match: dict[str, str] = field(default_factory=dict)  # draft id -> old id
    pieces: list[dict[str, Any]] = field(default_factory=list)  # title, summary, cards
    paths: dict[str, Any] = field(default_factory=dict)  # draft id -> path
    dropped: list[str] = field(default_factory=list)
    # The final audit: cards judged, per-rule failures of its first pass
    # (repaired or dropped since) and of the cards published (zero).
    audit: dict[str, Any] = field(default_factory=dict)
    sources: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        """The stored shape."""
        return asdict(self)

    def recs(self) -> dict[str, CardRec]:
        """The cards as records (draft ids)."""
        return {cid: CardRec.from_json(c) for cid, c in self.cards.items()}


def _match(
    ctx: Context, old: dict[str, CardRec], new: dict[str, CardRec]
) -> dict[str, str]:
    """New id -> old id, each side used once (the model's first pair wins)."""
    if not old or not new:
        return {}
    schema = prompts.match_schema(list(new), list(old))
    pairs = ctx.model(prompts.MATCH_SYSTEM, prompts.match(old, new), schema)
    found: dict[str, str] = {}
    raw = pairs.get("pairs")
    for pair in raw if isinstance(raw, list) else []:
        fresh = pair.get("new") if isinstance(pair, dict) else None
        was = pair.get("old") if isinstance(pair, dict) else None
        free = fresh not in found and was not in found.values()
        if fresh in new and was in old and free:
            found[fresh] = was
    return found


def _pieces(
    ctx: Context, scope: Scope, kept: dict[str, CardRec]
) -> list[dict[str, Any]]:
    """The module as pieces of at most 12 cards (one piece when it fits)."""
    module = scope.module
    whole = {"title": module.title, "summary": module.summary, "cards": list(kept)}
    if len(kept) <= prompts.MAX_PIECE:
        return [whole]
    raw = ctx.model(
        prompts.SPLIT_SYSTEM, prompts.split(scope, kept), prompts.SPLIT_SCHEMA
    )
    pieces = raw.get("pieces")
    found = (
        [p for p in pieces if isinstance(p, dict)] if (isinstance(pieces, list)) else []
    )
    ids = [c for p in found for c in p.get("cards") or []]
    sizes = [len(p.get("cards") or []) for p in found]
    fits = sizes and all(1 <= n <= prompts.MAX_PIECE for n in sizes)
    if (
        not fits
        or sorted(ids) != sorted(kept)
        or not all(p.get("title") for p in found)
    ):
        msg = f"the cut of {module.id} does not cover its {len(kept)} cards once each"
        raise RequestError(MODEL_ERROR, msg)
    return [
        {
            "title": " ".join(str(p["title"]).split())[:120],
            "summary": " ".join(str(p.get("summary", "")).split())[:300],
            "cards": list(p["cards"]),
        }
        for p in found
    ]


def _titles(found: list[wiki.Source]) -> dict[str, str]:
    return {s.url: s.title for s in found}


def _draft(
    ctx: Context, snap: Before, scope: Scope, found: list[wiki.Source]
) -> tuple[vet.Batch, vet.Vetted]:
    """The module drafted again and vetted against the seven rules."""
    limit = prompts.most(len(snap.live(scope.module.id)))
    system = prompts.draft_system(limit)
    raw = ctx.model(system, prompts.draft(scope, snap, found), CARDS_SCHEMA)
    items = raw.get("cards")
    batch = vet.Batch(scope, found, frozenset(snap.cards), limit=limit)
    return batch, vet.vet(ctx, batch, items if isinstance(items, list) else [])


def _finish(ctx: Context, scope: Scope, kept: dict[str, CardRec], out: Result) -> None:
    """The cut into pieces, each piece's paths, and the cards in piece order."""
    out.pieces = _pieces(ctx, scope, kept) if kept else []
    for piece in out.pieces:
        cards = {cid: kept[cid] for cid in piece["cards"]}
        about = f"{scope.about()}\nPiece: {piece['title']}"
        out.paths |= paths.draft(ctx, about, cards)
    out.cards = {cid: asdict(kept[cid]) for p in out.pieces for cid in p["cards"]}


def _others(snap: Before, module_id: str) -> dict[str, CardRec]:
    """What a new card must not repeat: the other modules' old live cards."""
    return {
        cid: c
        for cid, c in snap.cards.items()
        if not c.suspended and c.module != module_id
    }


def build(ctx: Context, snap: Before, module_id: str) -> Result:
    """Redraft ``module_id`` of ``snap``; ``ctx.model`` must be the draft tier.

    No source or a model failure raises ``RequestError``; a result with no
    card is returned as it is (``swap`` then keeps the old cards).
    """
    module = snap.plan.module(module_id)
    if module is None:
        msg = f"{snap.subject}/{module_id} is not in the snapshot"
        raise RequestError(MODEL_ERROR, msg)
    scope = Scope(snap.meta, module, snap.plan)
    old = snap.live(module_id)
    out = Result(snap.subject, module_id)
    found = gather.gather(ctx, scope, old)
    out.sources = [s.url for s in found]
    if not found:
        out.dropped = ["no readable source for this module"]
        return out
    batch, vetted = _draft(ctx, snap, scope, found)
    kept, refused = judge.gate(
        ctx, scope, vetted.kept, _titles(found), _others(snap, module_id)
    )
    matched = _match(ctx, old, kept)
    final = audit.run(
        ctx, batch, kept, {n for n, o in matched.items() if o in snap.hard}
    )
    out.audit = final.counts
    out.dropped = vetted.dropped + refused + final.dropped
    out.match = {n: o for n, o in matched.items() if n in final.kept}
    _finish(ctx, scope, final.kept, out)
    return out
