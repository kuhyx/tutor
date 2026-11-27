#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""F33: seed a sandbox for the model-free fallback (``e2e_sandbox.sh up``).

* ``outage <data> --reason R [--at T]`` (``up --outage R``): an open window
  in ``<data>/unavailable.jsonl`` the way ``unavailable.record`` writes one,
  from now (or the sandbox CLOCK ``T``) to two hours on, so the worker
  publishes ``stats.today.unavailable``.
* ``seed <data> --subject S --branch B [--at T]`` (``up --fallback B``): the
  copy's log so Start's chooser lands on branch B. The chooser of Home's
  Start looks at every subject, so nothing is due in any subject (within
  :data:`MARGIN_MS`, past the window and the sandbox's hour):

  - ``due``: S keeps (or gets) at least 2 cards due now;
  - ``read``: at least 3 readable cards (``pick.untaught``) in S's first
    teachable module;
  - ``drill``: every card of S's open modules is taught;
  - ``empty``: nothing of S taught, every card of its open modules
    flagged (read mode skips it) and the automation deck's ``cards_done``
    cleared (the drill adds that deck whatever is archived).

  ``drill`` and ``empty`` archive every other subject (Home shows S alone):
  their cards would send Start to read mode. Dues are cleared with drill
  reviews (``src: drill``), which never master a module, so the worker
  drafts nothing new. Writes ``<sandbox>/f33_seed.json``.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import logging
from pathlib import Path
import sys
import time
from typing import Any, Final

from e2e_fallback_state import Seeder, outage
from e2e_seed import DAY_MS, SeedError

from tutor import unavailable
from tutor.curriculum import pick
from tutor.curriculum.ids import ulid

_log = logging.getLogger(__name__)
BRANCHES: Final = ("due", "read", "drill", "empty")
DUE_MIN: Final = 2
READ_MIN: Final = 3
BACKDATE_MS: Final = 30 * DAY_MS  # taught a month ago: long due now


def _due(seeder: Seeder) -> dict[str, Any]:
    """S keeps at least 2 cards due now; nothing else is due."""
    cleared = seeder.clear_due(keep=seeder.subject)
    if len(seeder.due(seeder.target, seeder.now)) < DUE_MIN:
        # Fresh cards taught a month ago come due long before now.
        folded = seeder.ctx.fold()
        seen = {
            e.get("c") for e in seeder.ctx.log.read() if e.get("s") == seeder.subject
        }
        fresh = [c for c, _ in seeder.drafted(folded) if c not in seen][:DUE_MIN]
        seeder.worker_events("taught", fresh, seeder.now - BACKDATE_MS)
    due = seeder.due(seeder.target, seeder.now)
    if len(due) < DUE_MIN:
        msg = f"{seeder.subject} has {len(due)} card(s) due and no fresh card to add"
        raise SeedError(msg)
    return {"due": due, "cleared": cleared}


def _read(seeder: Seeder) -> dict[str, Any]:
    """At least 3 readable cards in S's first teachable module."""
    cleared = seeder.clear_due()
    if len(found := seeder.readable()) < READ_MIN:
        # Untaught the module's last taught cards: read mode opens it first.
        folded, view = seeder.ctx.fold(), seeder.target
        first = view.cards[found[0]].module if found else ""
        first = first or next((m.id for m in pick.teachable(view, folded)), "")
        taught = folded.taught_ids(seeder.subject)
        back = [c for c, _ in reversed(view.module_cards(first)) if c in taught]
        need = READ_MIN - len(found)
        seeder.worker_events("untaught", back[:need], seeder.now)
    found = seeder.readable()
    if len(found) < READ_MIN:
        msg = f"{seeder.subject} has only {len(found)} readable card(s): {found}"
        raise SeedError(msg)
    return {"read": found, "cleared": cleared}


def _drill(seeder: Seeder) -> dict[str, Any]:
    """Every card of S's teachable modules taught; Home holds S alone."""
    archived = seeder.archive_others()
    folded = seeder.ctx.fold()
    taught = folded.taught_ids(seeder.subject)
    fresh = [c for c, _ in seeder.drafted(folded) if c not in taught]
    seeder.worker_events("taught", fresh, seeder.now)
    cleared = seeder.clear_due()
    total = seeder.ctx.fold().taught_ids(seeder.subject)
    if seeder.readable() or not total:
        msg = f"{seeder.subject}: {len(total)} taught, {seeder.readable()} readable"
        raise SeedError(msg)
    return {
        "taught": len(total),
        "newly_taught": fresh,
        "archived": archived,
        "cleared": cleared,
    }


def _empty(seeder: Seeder) -> dict[str, Any]:
    """Nothing of S taught or readable; Home holds S alone; no deck done."""
    archived = seeder.archive_others()
    folded = seeder.ctx.fold()
    seeder.worker_events(
        "untaught", sorted(folded.taught_ids(seeder.subject)), seeder.now
    )
    at = seeder.now
    flags = [
        {
            "dev": seeder.ctx.device,
            "eid": ulid(at),
            "k": "flag",
            "s": seeder.subject,
            "c": cid,
            "at": at,
            "rev": rev,
            "reason": "e2e F33 empty",
        }
        for cid, rev in seeder.drafted(seeder.ctx.fold())
    ]
    seeder.ctx.log.append(flags)
    progress = seeder.data / "progress.json"
    if progress.is_file():
        saved = json.loads(progress.read_text(encoding="utf-8"))
        saved["cards_done"] = {}
        progress.write_text(json.dumps(saved, indent=1, ensure_ascii=False))
    if seeder.ctx.fold().taught_ids(seeder.subject) or seeder.readable():
        msg = f"{seeder.subject} still has taught or readable cards"
        raise SeedError(msg)
    return {"flagged": len(flags), "archived": archived}


SEEDERS: Final = {"due": _due, "read": _read, "drill": _drill, "empty": _empty}


def seed(data: Path, subject: str, branch: str, now: int) -> dict[str, Any]:
    """Seed ``branch`` for ``subject`` (module doc); returns what was seeded."""
    seeder = Seeder(data, subject, now)
    out = {"branch": branch, "subject": subject, **SEEDERS[branch](seeder)}
    (data.parent / "f33_seed.json").write_text(json.dumps(out))
    return out


def _now(at: str | None) -> float:
    """Unix seconds of the sandbox CLOCK (local time), else of now."""
    return datetime.fromisoformat(at).timestamp() if at else time.time()


def main(argv: list[str] | None = None) -> int:
    """CLI entry (see the module docstring); 1 when the seed is refused."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="what", required=True)
    one = sub.add_parser("outage")
    one.add_argument("--reason", choices=sorted(unavailable.REASONS), required=True)
    two = sub.add_parser("seed")
    two.add_argument("--subject", required=True)
    two.add_argument("--branch", choices=BRANCHES, required=True)
    for each in (one, two):
        each.add_argument("data", type=Path)
        each.add_argument("--at", help="the sandbox CLOCK, YYYY-MM-DD HH:MM:SS")
    args = parser.parse_args(argv)
    now = _now(args.at)
    try:
        if args.what == "outage":
            window = outage(args.data, args.reason, now)
            line = f"e2e seed F33: {window.reason} outage until {window.end}"
        else:
            found = seed(args.data, args.subject, args.branch, int(now * 1000))
            line = f"e2e seed F33: {json.dumps(found)}"
    except SeedError as err:
        _log.error("e2e_fallback_seed: %s", err)  # `up` stops on exit 1
        return 1
    sys.stdout.write(line + "\n")  # the seed's evidence in `up`'s output
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
