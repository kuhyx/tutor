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
    row = phase_row("solve" if mode == "solve" else "theory", pairs, key)
    if mode == "bad":
        row["hmac"] = "0" * 64
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(row), encoding="utf-8")
    return f"{mode} {row['detail']['teachable']}"


def seed(data: Path, subject: str, module: str) -> str:
    """Teach all of ``module`` but its first untaught live card; that card."""
    _sandboxed(data)
    ctx = Context(data, device=str(uuid.uuid4()))
    cards = ctx.subjects.cards(subject)
    folded = fold(ctx.log.read())
    untaught = [
        cid
        for cid, card in cards.items()
        if card.module == module
        and not card.suspended
        and not folded.card(subject, cid).taught
    ]
    if not untaught:
        msg = f"{subject}/{module} has no untaught live card"
        raise PhaseError(msg)
    at = int((time.time() - 2 * DAY_S) * 1000)
    ctx.log.append(
        [
            worker_event("taught", (subject, c), dev=ctx.device, at=at)
            for c in untaught[1:]
        ]
    )
    left = {"subject": subject, "module": module, "card": untaught[0]}
    (data.parent / "c4_seed.json").write_text(json.dumps(left), encoding="utf-8")
    return untaught[0]


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
