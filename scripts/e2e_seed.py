#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Seed an agent-E2E sandbox's data dir (``scripts/e2e_sandbox.sh up``).

* ``struggle <data> --subject S`` (F5): two Again reviews, from a fresh "app"
  device at the card's current ``rev``, 61 s apart, right after the card's
  last event, on the first taught card of S that is then due, first in S's
  due queue (by the Python fold, the same as the app's) and struggling 2.
  The app's own Again is the third: the offer's 3. Writes
  ``<sandbox>/f5_seed.json`` with the card, its front and a known untaught
  card of S (``bad_request`` for a struggle).
* ``carry <data> --key K --day D --minutes N`` (F6): signed credit rows
  ending on local day D, N minutes in all, into ``<data>/ledger.json`` with
  the sandbox key K. Refuses the real data dir and the real key.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime
import json
from pathlib import Path
import sys
import time
from typing import TYPE_CHECKING, Any, Final
import uuid

import earned_time

from tutor.curriculum.context import Context
from tutor.curriculum.eventlog import review_event
from tutor.curriculum.fold import Fold, fold
from tutor.ledger_io import read_rows, write_rows

if TYPE_CHECKING:
    from tutor.curriculum.records import CardRec

REAL_DATA: Final = Path.home() / ".local" / "share" / "tutor"
REAL_KEY: Final = Path("/etc/workout-locker/hmac.key")
GAP_MS: Final = 61_000  # past the fold's 60 s cross-device dedupe
AGAIN: Final = 1
SEEDED_RUN: Final = 2  # the app's Again makes it 3
ROW_MINUTES: Final = 50


class SeedError(RuntimeError):
    """The sandbox cannot be seeded as asked."""


def _sandboxed(data: Path) -> None:
    real = REAL_DATA.resolve()
    if data.resolve() == real or real in data.resolve().parents:
        msg = f"refusing to seed the real data dir {data}"
        raise SeedError(msg)


def _queue(
    events: list[dict[str, Any]], cards: dict[str, CardRec], s: str, now: int
) -> tuple[list[tuple[int, str]], Fold]:
    """The subject's due queue ``[(due, card)]``, as the app sorts it."""
    folded = fold(events)
    due = []
    for cid, rec in cards.items():
        state = folded.card(s, cid)
        sched = state.fsrs_state()
        if rec.suspended or sched is None or state.flagged(rec.rev):
            continue
        if sched["due"] <= now:
            due.append((sched["due"], cid))
    return sorted(due), folded


def struggle(data: Path, subject: str, now: int) -> dict[str, str]:
    """Seed two Again ratings on a card that then leads the due queue (module doc)."""
    _sandboxed(data)
    ctx = Context(data, device=str(uuid.uuid4()))
    cards = ctx.subjects.cards(subject)
    events = ctx.log.read()
    folded = fold(events)
    last: dict[str, int] = {}
    for e in events:
        if e.get("s") == subject and e.get("c") in cards:
            last[e["c"]] = max(last.get(e["c"], 0), int(e["at"]))
    taught = sorted((at, c) for c, at in last.items() if folded.card(subject, c).taught)
    for at, cid in taught:
        rev = cards[cid].rev
        seeds = [
            review_event(
                (subject, cid), AGAIN, dev=ctx.device, span=(t - 5000, t), rev=rev
            )
            for t in (at + GAP_MS, at + 2 * GAP_MS)
        ]
        queue, after = _queue([*events, *seeds], cards, subject, now)
        if (
            queue
            and queue[0][1] == cid
            and after.card(subject, cid).struggle(rev) == SEEDED_RUN
        ):
            ctx.log.append(seeds)
            untaught = next(c for c in cards if not folded.card(subject, c).taught)
            seed = {
                "subject": subject,
                "card": cid,
                "front": cards[cid].front,
                "untaught": untaught,
                "due": str(len(queue)),  # Home's tile: "Review (<due> due)"
            }
            (data.parent / "f5_seed.json").write_text(json.dumps(seed))
            return seed
    msg = f"no taught card of {subject} can lead its due queue"
    raise SeedError(msg)


def carry(data: Path, key_file: Path, day: date, minutes: int) -> list[str]:
    """Signed rows paying ``minutes`` on ``day`` (local), appended to the ledger."""
    _sandboxed(data)
    if key_file.resolve() == REAL_KEY.resolve():
        msg = "refusing to sign with the real key"
        raise SeedError(msg)
    key = key_file.read_bytes().strip()
    ledger = data / "ledger.json"
    rows: list[object] = read_rows(ledger) if ledger.is_file() else []
    ids, left, hour = [], minutes, 9
    while left > 0:
        paid = min(ROW_MINUTES, left)
        ended = datetime.combine(day, datetime.min.time()).replace(hour=hour)
        sid = f"{day:%Y%m%d}-{hour:02d}0000-e2e{hour % 10}"
        row: dict[str, Any] = {
            "kind": "credit",
            "entry_id": f"{sid}-m{paid}",
            "day": day.isoformat(),
            "created_at": ended.timestamp(),
            "detail": {
                "session_id": sid,
                "block": paid,
                "minutes": paid,
                "active_seconds": paid * 60.0,
                "ended_at": ended.astimezone().timestamp(),
                "checks_passed": 1,
                "checks_total": 1,
            },
        }
        row["hmac"] = str(earned_time.entry_signature(row, key))
        rows.append(row)
        ids.append(row["entry_id"])
        left, hour = left - paid, hour + 1
    write_rows(ledger, rows)
    return ids


def main() -> int:
    """CLI entry (see the module docstring)."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="what", required=True)
    one = sub.add_parser("struggle")
    one.add_argument("data", type=Path)
    one.add_argument("--subject", required=True)
    two = sub.add_parser("carry")
    two.add_argument("data", type=Path)
    two.add_argument("--key", type=Path, required=True)
    two.add_argument("--day", type=date.fromisoformat, required=True)
    two.add_argument("--minutes", type=int, required=True)
    args = parser.parse_args()
    if args.what == "struggle":
        found = struggle(args.data, args.subject, int(time.time() * 1000))
        line = f"e2e seed F5: 2 Again on {found['card']}; untaught {found['untaught']}"
    else:
        ids = carry(args.data, args.key, args.day, args.minutes)
        line = f"e2e seed F6: {args.minutes} min on {args.day}: {ids}"
    sys.stdout.write(line + "\n")  # the seed's evidence in `up`'s output
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
