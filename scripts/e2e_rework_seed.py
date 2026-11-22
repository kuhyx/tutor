#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``up --rework S/M/SLUG``: the sandbox side of flow F29 (``e2e_rework.py``).

* ``<sandbox>/guard/history/<SLUG>.json``: a synthetic leetcode-guard history
  of the problem (two submissions with code), in the shape of the guard's
  ``_history_store``. The sandbox server reads it through
  ``TUTOR_GUARD_DATA=<sandbox>/guard`` (``_e2e_sandbox_units.sh``), never the
  guard's live dir.
* Module M of S is made done: every untaught live card becomes taught (worker
  ``taught`` events), then ``module_state.reconcile`` writes the truth of every
  module of S. The latest row of S/M verified with the sandbox key must read
  ``done: true``: the copied rows are signed with the real key and do not
  verify here, and with no verified row the rework's untaught card would
  write no ``done: false`` row at all (``reconcile`` skips a not-done module
  with no row).

Refuses the real data dirs (``e2e_phase.REAL``) and needs ``TUTOR_KEY``.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time
import uuid

from e2e_phase import DAY_S, PhaseError, _sandboxed, untaught
from gatelock import log_integrity

from tutor.curriculum import module_state
from tutor.curriculum.context import Context
from tutor.curriculum.eventlog import worker_event

# Wrong Answer first (the centre cell of an odd n counted twice), then the fix.
WRONG = (
    "function diagonalSum(mat: number[][]): number {\n"
    "  const n = mat.length;\n  let s = 0;\n"
    "  for (let i = 0; i < n; i++) s += mat[i][i] + mat[i][n - 1 - i];\n"
    "  return s;\n}"
)
RIGHT = (
    "function diagonalSum(mat: number[][]): number {\n"
    "  const n = mat.length;\n  let s = 0;\n"
    "  for (let i = 0; i < n; i++) s += mat[i][i] + mat[i][n - 1 - i];\n"
    "  return n % 2 ? s - mat[n >> 1][n >> 1] : s;\n}"
)


def history(slug: str, now: float) -> dict[str, object]:
    """The guard's ``history/<slug>.json`` with two submissions."""
    rows = [
        ("e2e-1", "Wrong Answer", WRONG, now - 2 * DAY_S, "N/A", "N/A"),
        ("e2e-2", "Accepted", RIGHT, now - DAY_S, "0 ms", "56.8 MB"),
    ]
    return {
        "slug": slug,
        "fetched_at": now,
        "complete": True,
        "submissions": [
            {
                "id": sid,
                "status": status,
                "lang": "typescript",
                "timestamp": int(at),
                "runtime": runtime,
                "memory": memory,
                "code": code,
            }
            for sid, status, code, at, runtime, memory in rows
        ],
    }


def done_row(data: Path, subject: str, module: str, key: Path) -> bool | None:
    """``done`` of the latest sandbox-verified C2 row of S/M (None: no row)."""
    rows = json.loads((data / "module_state.json").read_text(encoding="utf-8"))
    mine = [
        r
        for r in rows.get("entries", [])
        if (r.get("detail") or {}).get("subject") == subject
        and r["detail"].get("module") == module
        and log_integrity.verify_entry_hmac(r, key_file=key)
    ]
    return bool(mine[-1]["detail"]["done"]) if mine else None


def seed(sandbox: Path, subject: str, module: str, slug: str) -> str:
    """Write the history and make S/M done; a one-line summary."""
    data, key = sandbox / "data", sandbox / "test.key"
    _sandboxed(sandbox, data, key)
    now = time.time()
    path = sandbox / "guard" / "history" / f"{slug}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history(slug, now)), encoding="utf-8")
    ctx = Context(data, device=str(uuid.uuid4()))
    left = untaught(ctx, subject, module)
    at = int((now - 2 * DAY_S) * 1000)
    ctx.log.append(
        [worker_event("taught", (subject, c), dev=ctx.device, at=at) for c in left]
    )
    module_state.reconcile(data, subject, now, backfill_all=True)
    if done_row(data, subject, module, key) is not True:
        msg = f"{subject}/{module} has no verified done: true row after the seed"
        raise PhaseError(msg)
    return f"e2e seed F29: {path.name}, {subject}/{module} done ({len(left)} taught)"


def main() -> int:
    """CLI entry (see the module docstring)."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sandbox", type=Path)
    parser.add_argument("target", help="SUBJECT/MODULE/SLUG")
    args = parser.parse_args()
    want = (args.sandbox / "test.key").resolve()
    if Path(os.environ.get("TUTOR_KEY", "/")).resolve() != want:
        msg = f"seed needs TUTOR_KEY={want} (the sandbox key)"
        raise PhaseError(msg)
    subject, module, slug = args.target.split("/")
    sys.stdout.write(seed(args.sandbox, subject, module, slug) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
