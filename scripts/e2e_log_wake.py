#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Agent-E2E flow F30: a review from another device reaches the PC in < 5 s.

Runs on a plain ``e2e_sandbox.sh up`` (no browser, no model). A fake phone
device (a fresh uuid) writes review events to ``log/{dev}`` on the emulator
as the app does (``review_event``, sealed like every unit). Phases, one call
each:

* ``rate``: three ratings; for each, the delay from the write to its eid in
  the sandbox ``log.jsonl``. Then one more rating on a queued card of a
  watched subject (``module_state.SUBJECTS``): the delay to the change of
  ``review_due.json``'s mtime. Any delay over :data:`LIMIT_S` fails.
* ``idle`` (75 until 60 s after ``rate``): over that window the worker's
  own ``log/`` node did not move and its CPU stayed under
  :data:`IDLE_CPU_S`, so its own push set off no sync loop.
"""

from __future__ import annotations

import argparse
from functools import partial
import hashlib
import json
import logging
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import TYPE_CHECKING, Any, Final
import uuid

from e2e_flow import Emulator, FlowError

from tutor.curriculum.context import Context
from tutor.curriculum.eventlog import review_event
from tutor.curriculum.module_state import SUBJECTS
from tutor.curriculum.review_due import FILE

if TYPE_CHECKING:
    from collections.abc import Callable

_logger = logging.getLogger(__name__)
RATINGS: Final = 3  # to log.jsonl; one more to review_due.json
SYSTEMCTL: Final = shutil.which("systemctl") or "/usr/bin/systemctl"
LIMIT_S: Final = 5.0
IDLE_S: Final = 60.0
IDLE_CPU_S: Final = 10.0
PENDING: Final = 75
ROOT: Final = Path(__file__).resolve().parent.parent


def _unit() -> str:
    """The sandbox server unit (``e2e_sandbox.sh``: md5 of the checkout)."""
    tag = hashlib.md5(str(ROOT).encode(), usedforsecurity=False).hexdigest()[:8]
    return f"tutor-e2e-server-{tag}"


def _cpu_s() -> float:
    out = subprocess.run(
        [SYSTEMCTL, "--user", "show", "-p", "CPUUsageNSec", "--value", _unit()],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return int(out) / 1e9


def _queued(data: Path) -> list[tuple[str, str, int]]:
    """``(subject, card, rev)`` of review-queue cards of the watched subjects."""
    ctx = Context(data)
    folded = ctx.fold()
    found = []
    for subject in sorted(SUBJECTS & set(ctx.subjects.subjects())):
        for cid, rec in ctx.subjects.cards(subject).items():
            state = folded.card(subject, cid)
            if not rec.suspended and state.fsrs_state() and not state.flagged(rec.rev):
                found.append((subject, cid, rec.rev))
    return found


def _landed(log: Path, eid: str) -> bool:
    return f'"{eid}"' in log.read_text(encoding="utf-8")


def _rate(db: Emulator, dev: str, card: tuple[str, str, int]) -> tuple[str, float]:
    """Write one ``good`` review as the phone; ``(eid, write time)``."""
    subject, cid, rev = card
    now = int(time.time() * 1000)
    event = review_event((subject, cid), 3, dev=dev, span=(now - 4000, now), rev=rev)
    eid = event.pop("eid")
    del event["dev"]
    start = time.time()
    db.put(f"log/{dev}/{eid}", event)
    return eid, start


def _until(check: Callable[[], bool], start: float, what: str) -> float:
    """Seconds from ``start`` until ``check()`` holds; fails past 2 x LIMIT_S."""
    while not check():
        if time.time() - start > 2 * LIMIT_S:
            msg = f"{what}: nothing after {2 * LIMIT_S:.0f} s"
            raise FlowError(msg)
        time.sleep(0.05)
    return time.time() - start


def rate(db: Emulator, data: Path, worker: str) -> dict[str, Any]:
    """Three ratings to ``log.jsonl``, one more to ``review_due.json``."""
    cards = _queued(data)
    if len(cards) <= RATINGS:
        msg = (
            f"want {RATINGS + 1} queued cards of {sorted(SUBJECTS)}, have {len(cards)}"
        )
        raise FlowError(msg)
    dev, log, due = str(uuid.uuid4()), data / "log.jsonl", data / FILE
    _logger.info("F30 phone device %s; worker %s", dev, worker)
    delays = []
    for n, card in enumerate(cards[:RATINGS], 1):
        eid, start = _rate(db, dev, card)
        delay = _until(partial(_landed, log, eid), start, eid)
        _logger.info("F30 rating %d (%s): write -> log.jsonl %.2f s", n, card[1], delay)
        delays.append(delay)
    before = due.stat().st_mtime
    _, start = _rate(db, dev, cards[RATINGS])
    moved = _until(lambda: due.stat().st_mtime != before, start, "review_due.json")
    _logger.info(
        "F30 rating 4 (%s): write -> review_due.json mtime %.2f s",
        cards[RATINGS][1],
        moved,
    )
    if (worst := max([*delays, moved])) > LIMIT_S:
        msg = f"a delay of {worst:.2f} s is over {LIMIT_S:.0f} s"
        raise FlowError(msg)
    own = sorted(db.node(f"log/{worker}"))
    return {"at": time.time(), "cpu": _cpu_s(), "own": len(own), "delays": delays}


def idle(db: Emulator, worker: str, state: dict[str, Any]) -> int:
    """No sync loop: the own node is still, the CPU low, over 60 s."""
    waited = time.time() - float(state["at"])
    if waited < IDLE_S:
        _logger.info("PENDING F30 idle: %.0f of %.0f s; call again", waited, IDLE_S)
        return PENDING
    cpu, own = _cpu_s() - float(state["cpu"]), len(db.node(f"log/{worker}"))
    _logger.info("F30 idle %.0f s: worker CPU %.2f s, own events %d", waited, cpu, own)
    if own != state["own"] or cpu > IDLE_CPU_S:
        msg = f"own events {state['own']} -> {own}, CPU {cpu:.2f} s: a sync loop?"
        raise FlowError(msg)
    return 0


def main() -> int:
    """CLI entry: the arguments ``e2e_sandbox.sh flow`` passes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("flow", choices=["F30"])
    parser.add_argument("phase", choices=["rate", "idle"])
    for name in ("--app", "--card", "--out", "--session", "--subject", "--display"):
        parser.add_argument(name)
    parser.add_argument("--db", required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--focus", type=Path)
    parser.add_argument("--state", type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(stream=sys.stdout, format="%(message)s", level=logging.INFO)
    db = Emulator(args.db)
    worker = (args.data / "device_id").read_text(encoding="utf-8").strip()
    try:
        if args.phase == "rate":
            args.state.write_text(json.dumps(rate(db, args.data, worker)))
        elif (code := idle(db, worker, json.loads(args.state.read_text()))) != 0:
            return code
    except (FlowError, OSError, ValueError) as err:
        _logger.warning("FAIL F30 %s: %s", args.phase, err)
        return 1
    _logger.info("PASS F30 %s", args.phase)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
