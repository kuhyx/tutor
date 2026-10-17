#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Copy the tutor data dir into an agent-E2E sandbox (``scripts/e2e_sandbox.sh``).

The copy never carries the ledger (its rows are signed with the real key),
the server log, the model's scratch cwd or the device id: the sandbox worker
gets a fresh uuid4, and every mention of the live worker's id is rewritten
to it, so nothing the sandbox writes can be mistaken for (or claim the
requests of) the live ``tutor.service``. ``--new-cap N`` appends a Settings
``new_cap`` event from a fresh "app" device, as the app's Settings screen
would, to force the daily new-card limit. ``--as-of "YYYY-MM-DD HH:MM"``
(local time) rewinds the copy to that moment: later log events, session
transcripts and drill logs are dropped, so a reported state can be replayed
after kuhy has moved on.

Usage: e2e_prepare.py <src> <empty dst> [--new-cap N] [--as-of "YYYY-MM-DD HH:MM"]
Prints the sandbox worker's device id.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import shutil
import time
from typing import Final
import uuid

from tutor.curriculum.ids import ulid

REAL_DATA: Final = Path.home() / ".local" / "share" / "tutor"
# Top-level entries never copied (see the module docstring).
SKIPPED: Final = frozenset(
    {"ledger.json", "ledger.lock", "server.log", "sandbox", "device_id"}
)


class PrepareError(RuntimeError):
    """The sandbox cannot be made safely."""


def _inside(path: Path, root: Path) -> bool:
    return path.resolve() == root.resolve() or root.resolve() in path.resolve().parents


def _rewrite(root: Path, old: str, new: str) -> None:
    """Replace ``old`` with ``new`` in every file under ``root``."""
    for path in root.rglob("*"):
        if path.is_file():
            raw = path.read_bytes()
            if old.encode() in raw:
                path.write_bytes(raw.replace(old.encode(), new.encode()))


def _leftovers(root: Path, old: str) -> list[Path]:
    return [
        p for p in root.rglob("*") if p.is_file() and old.encode() in p.read_bytes()
    ]


def new_cap_event(cap: int, at_ms: int) -> dict[str, object]:
    """A Settings ``new_cap`` event from a fresh app device (curriculum §4)."""
    return {
        "dev": str(uuid.uuid4()),
        "eid": ulid(at_ms),
        "k": "new_cap",
        "n": cap,
        "at": at_ms,
    }


def _started(path: Path) -> datetime | None:
    """The local start time in a ``[drill-]YYYYMMDD-HHMMSS-xxxx.jsonl`` name."""
    stamp = path.stem.removeprefix("drill-")[:15]
    if not re.fullmatch(r"\d{8}-\d{6}", stamp):
        return None
    return datetime.strptime(stamp, "%Y%m%d-%H%M%S").astimezone()


def rewind(root: Path, as_of: datetime) -> int:
    """Drop what happened at or after ``as_of``; returns how much was dropped."""
    cut = int(as_of.timestamp() * 1000)
    log = root / "log.jsonl"
    lines = log.read_text(encoding="utf-8").splitlines() if log.is_file() else []
    kept = [line for line in lines if line and json.loads(line).get("at", 0) < cut]
    log.write_text("".join(f"{line}\n" for line in kept), encoding="utf-8")
    dropped = len(lines) - len(kept)
    for path in [*root.glob("sessions/*.jsonl"), *root.glob("drill/*.jsonl")]:
        started = _started(path)
        if started is not None and started >= as_of:
            path.unlink()
            dropped += 1
    return dropped


def prepare(
    src: Path, dst: Path, *, new_cap: int | None = None, as_of: datetime | None = None
) -> str:
    """Copy ``src`` to ``dst`` for a sandbox run; returns the new device id."""
    if _inside(dst, REAL_DATA) or _inside(dst, src):
        msg = f"refusing to write the sandbox inside {src} or {REAL_DATA}"
        raise PrepareError(msg)
    if dst.exists() and any(dst.iterdir()):
        msg = f"{dst} is not empty"
        raise PrepareError(msg)
    old = (src / "device_id").read_text(encoding="utf-8").strip()
    shutil.copytree(
        src,
        dst,
        ignore=lambda d, names: SKIPPED & set(names) if Path(d) == src else set(),
        dirs_exist_ok=True,
    )
    new = str(uuid.uuid4())
    (dst / "device_id").write_text(f"{new}\n", encoding="utf-8")
    if old:
        _rewrite(dst, old, new)
        if left := _leftovers(dst, old):
            msg = f"live device id still in {left}"
            raise PrepareError(msg)
    if as_of is not None:
        rewind(dst, as_of)
    if new_cap is not None:
        line = json.dumps(new_cap_event(new_cap, int(time.time() * 1000)))
        with (dst / "log.jsonl").open("a", encoding="utf-8") as log:
            log.write(line + "\n")
    return new


def main() -> int:
    """CLI entry (see the module docstring)."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("src", type=Path)
    parser.add_argument("dst", type=Path)
    parser.add_argument("--new-cap", type=int, choices=range(1, 201), metavar="1..200")
    parser.add_argument(
        "--as-of",
        type=lambda raw: datetime.strptime(raw, "%Y-%m-%d %H:%M").astimezone(),
        help='rewind the copy to this local time, "YYYY-MM-DD HH:MM"',
    )
    args = parser.parse_args()
    print(prepare(args.src, args.dst, new_cap=args.new_cap, as_of=args.as_of))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
