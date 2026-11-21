# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Export the live ``automation`` subject back to the repo deck.

After a redraft the subject on disk is ahead of ``subjects/automation/deck``
(the seed of a fresh install, ``migrate``). :func:`export` rewrites the deck
from the subject: one topic file per plan module (the module id with ``_``
for ``-``), its live cards in teaching order, and ``manifest.json`` naming
the topics in plan order. A topic file the plan no longer has is removed.
The result is loaded back through ``cards.load_deck`` rules before anything
is written, so a deck the loader would refuse is never left behind.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Final

from tutor import cards
from tutor.curriculum import card_rules
from tutor.curriculum.errors import BAD_REQUEST, RequestError

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.curriculum.context import Context
    from tutor.curriculum.records import CardRec

SUBJECT: Final = "automation"


def _item(cid: str, rec: CardRec) -> dict[str, Any]:
    out = card_rules.raw(cid, rec)
    if not rec.requires:
        del out["requires"]  # the deck files leave an empty list out
    return out


def _dump(path: Path, data: object) -> None:
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def export(ctx: Context, deck_dir: Path) -> dict[str, int]:
    """Rewrite ``deck_dir`` from the live subject; returns stem -> card count.

    ``bad_request`` when the subject has no plan or its cards break the deck
    rules (nothing is written then).
    """
    plan = ctx.subjects.plan(SUBJECT)
    if plan is None:
        msg = f"no {SUBJECT} subject in {ctx.data_dir}"
        raise RequestError(BAD_REQUEST, msg)
    found = {c: r for c, r in ctx.subjects.cards(SUBJECT).items() if not r.suspended}
    try:
        card_rules.check_set(found, {m.id: m for m in plan.modules})
    except cards.CardError as err:
        raise RequestError(BAD_REQUEST, str(err)) from err
    files: dict[str, list[dict[str, Any]]] = {}
    manifest: list[dict[str, Any]] = []
    for module in plan.modules:
        own = sorted(
            ((c, r) for c, r in found.items() if r.module == module.id),
            key=lambda item: item[1].order,
        )
        if not own:
            continue
        stem = module.id.replace("-", "_")
        files[stem] = [_item(cid, rec) for cid, rec in own]
        manifest.append(
            {"stem": stem, "title": module.title, "prefixes": list(module.prefixes)}
        )
    deck_dir.mkdir(parents=True, exist_ok=True)
    for old in deck_dir.glob("*.json"):
        if old.stem not in files:
            old.unlink()  # a retired topic (and the old manifest)
    for stem, items in files.items():
        _dump(deck_dir / f"{stem}.json", items)
    _dump(deck_dir / cards.MANIFEST, manifest)
    return {stem: len(items) for stem, items in files.items()}
