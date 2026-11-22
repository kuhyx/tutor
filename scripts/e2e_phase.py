#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The guard's side of C3 in an agent-E2E sandbox (``scripts/e2e_sandbox.sh``).

* ``write <path> --key K theory S/M [S/M ...] | solve | bad | missing``: the
  guard's ``theory_phase.json`` as leetcode-guard writes it, signed with
  ``gatelock.log_integrity`` (the guard's library) and the sandbox key K.
  ``theory`` grants exactly the listed (subject, module) pairs, ``solve``
  grants nothing, ``bad`` is a ``theory`` row granting S/M whose ``hmac``
  does not match, ``missing`` deletes the file.
* ``seed <data> --subject S --module M``: every live card of M but its first
  untaught one becomes taught (worker ``taught`` events), so teaching that one
  card finishes the module (C2 ``done: true``). Prints the card left and
  writes it to ``<sandbox>/c4_seed.json`` for the flows.

Both refuse the real data dir, the guard's real file and the real key.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Final
import uuid

from gatelock import log_integrity

from tutor.curriculum import theory_phase
from tutor.curriculum.context import Context
from tutor.curriculum.eventlog import worker_event
from tutor.curriculum.fold import fold

REAL: Final = (
    Path.home() / ".local/share/tutor",
    Path.home() / ".local/share/leetcode_guard",
    Path("/etc/workout-locker"),
)
DAY_S: Final = 86_400
_PAIR: Final = 2


class PhaseError(RuntimeError):
    """The sandbox cannot be set up as asked."""


def _sandboxed(*paths: Path) -> None:
    for path in paths:
        where = path.resolve()
        for real in REAL:
            if where == real.resolve() or real.resolve() in where.parents:
                msg = f"refusing a real path: {path}"
                raise PhaseError(msg)


def phase_row(phase: str, pairs: list[list[str]], key: Path) -> dict[str, Any]:
    """The guard's signed row (``DOCS-contract-theory-phase.md``)."""
    body: dict[str, Any] = {
        "kind": "theory_phase",
        "entry_id": "phase",
        "day": time.strftime("%Y-%m-%d"),
        "detail": {
            "unit": pairs[0][1] if pairs else "",
            "phase": phase,
            "teachable": pairs,
            "at": time.time(),
        },
    }
    return body | {"hmac": log_integrity.compute_entry_hmac(body, key_file=key)}


def write(path: Path, key: Path, mode: str, specs: list[str]) -> str:
    """Write (or delete) the phase file; a one-line summary."""
    _sandboxed(path, key)
    if mode == "missing":
        path.unlink(missing_ok=True)
        return f"no {path.name}"
    pairs = [spec.split("/", 1) for spec in specs]
    if mode == "solve":
        pairs = []
    elif not pairs or any(len(p) != _PAIR for p in pairs):
        msg = f"{mode} needs SUBJECT/MODULE pairs, got {specs}"
        raise PhaseError(msg)
    # A pair of an ungated subject (e.g. a bare "LC" for its full id) grants
    # nothing: the flow would fail later as a misleading no_card_left.
    if wrong := sorted({p[0] for p in pairs} - theory_phase.GATED):
        msg = f"not a gated subject id: {wrong}; one of {sorted(theory_phase.GATED)}"
        raise PhaseError(msg)
    row = phase_row("solve" if mode == "solve" else "theory", pairs, key)
    if mode == "bad":
        row["hmac"] = "0" * 64
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(row), encoding="utf-8")
    return f"{mode} {row['detail']['teachable']}"


def untaught(ctx: Context, subject: str, module: str | None = None) -> list[str]:
    """The live untaught cards of ``subject`` (of ``module`` if given), in order."""
    cards = ctx.subjects.cards(subject)
    folded = fold(ctx.log.read())
    return [
        cid
        for cid, card in cards.items()
        if module in {None, card.module}
        and not card.suspended
        and not folded.card(subject, cid).taught
    ]


def quiet_today(data: Path) -> int:
    """Move today's transcripts out of the sandbox copy; how many moved.

    The sandbox ledger starts empty, so the worker's startup backfill pays
    kuhy's real sessions of today again and can fill the daily cap before a
    flow's own C1 row (2026-11-22: 102 of 160 minutes, "daily cap"). The
    event log keeps their events; only the transcripts move, beside ``data``.
    """
    _sandboxed(data)
    held = data.parent / "today-sessions"
    held.mkdir(exist_ok=True)
    found = sorted((data / "sessions").glob(time.strftime("%Y%m%d") + "-*.jsonl"))
    for path in found:
        path.rename(held / path.name)
    return len(found)


def _openable(ctx: Context, subject: str, module: str) -> list[str]:
    """``module``'s live cards whose requires are in it or already taught.

    Only such a card can be left untaught: the pick skips a card that needs
    an untaught card of another module (kuhy's real progress decides which).
    """
    cards = ctx.subjects.cards(subject)
    folded = fold(ctx.log.read())
    taught = folded.taught_ids(subject)
    return [
        cid
        for cid, card in cards.items()
        if card.module == module
        and not card.suspended
        and all(
            need in taught or getattr(cards.get(need), "module", "") == module
            for need in card.requires
        )
    ]


def seed(data: Path, subject: str, module: str) -> str:
    """Teach all of ``module`` but one openable card; that card.

    The card is the first openable untaught one, else (kuhy taught them all)
    the first openable card, taken back by an ``untaught`` event newer than
    any real one.
    """
    quiet_today(data)
    ctx = Context(data, device=str(uuid.uuid4()))
    cards_left = untaught(ctx, subject, module)
    openable = _openable(ctx, subject, module)
    if not openable:
        msg = f"{subject}/{module} has no card whose requires can be met"
        raise PhaseError(msg)
    card = next((c for c in openable if c in cards_left), openable[0])
    now = int(time.time() * 1000)
    at = now - 2 * DAY_S * 1000
    events = [
        worker_event("taught", (subject, c), dev=ctx.device, at=at)
        for c in cards_left
        if c != card
    ]
    if card not in cards_left:
        events.append(worker_event("untaught", (subject, card), dev=ctx.device, at=now))
    ctx.log.append(events)
    left = {"subject": subject, "module": module, "card": card}
    (data.parent / "c4_seed.json").write_text(json.dumps(left), encoding="utf-8")
    return card


def main() -> int:
    """CLI entry (see the module docstring)."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="what", required=True)
    one = sub.add_parser("write")
    one.add_argument("path", type=Path)
    one.add_argument("--key", type=Path, required=True)
    one.add_argument("mode", choices=["theory", "solve", "bad", "missing"])
    one.add_argument("pairs", nargs="*", help="SUBJECT/MODULE")
    two = sub.add_parser("seed")
    two.add_argument("data", type=Path)
    two.add_argument("--subject", required=True)
    two.add_argument("--module", required=True)
    args = parser.parse_args()
    if args.what == "write":
        line = f"e2e phase: {write(args.path, args.key, args.mode, args.pairs)}"
    else:
        # The seed's own C2 rows are signed with the sandbox key, never the real one.
        if not os.environ.get("TUTOR_KEY"):
            msg = "seed needs TUTOR_KEY (the sandbox key)"
            raise PhaseError(msg)
        card = seed(args.data, args.subject, args.module)
        line = f"e2e seed C4: {args.subject}/{args.module} left untaught: {card}"
    sys.stdout.write(line + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
