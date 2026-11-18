# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Archive a subject, and undo it (``DOCS-relay-kinds.md`` "Archived subjects").

``subject_archive`` / ``subject_unarchive`` (build lane) append one worker
event each to the append-only log; nothing else is written. While the latest
one is ``subject_archive``:

* ``SubjectStore.subjects()`` leaves the subject out, so nothing advances,
  generates or publishes it, and the worker deletes ``subjects/{id}`` from
  RTDB (``CurriculumSync``): Home on every device drops it;
* ``Context.fold()`` masks its cards and events: nothing in it counts as
  taught, reviewed or new today, and ``SubjectSource.pick`` refuses it;
* its files, transcripts and ids stay. Undo appends ``subject_unarchive``,
  and the fold of the unchanged history gives back exactly the old state.

The earned-time ledger is never touched. ``python -m tutor subject
archive|unarchive ID [--data DIR]`` runs the same handlers on a data dir
(the live one by default); the live worker publishes the event and updates
the catalog on its next sync (within a minute).
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys
from typing import TYPE_CHECKING, Any, Final

from tutor.curriculum.context import Context
from tutor.curriculum.errors import RequestError
from tutor.curriculum.eventlog import ARCHIVE, UNARCHIVE
from tutor.curriculum.ids import ulid, valid_id
from tutor.curriculum.records import bad
from tutor.store import data_dir

if TYPE_CHECKING:
    from collections.abc import Callable

_logger = logging.getLogger(__name__)


def subject_event(kind: str, subject: str, *, dev: str, at: int) -> dict[str, Any]:
    """The worker's ``subject_archive`` / ``subject_unarchive``, fresh eid."""
    return {"dev": dev, "eid": ulid(at), "k": kind, "s": subject, "at": at}


def _toggle(body: dict[str, Any], ctx: Context, *, archive: bool) -> dict[str, Any]:
    """Append the event unless the subject is already in that state."""
    subject = body.get("subject")
    if not valid_id(subject):
        msg = "subject must be a subject id"
        raise bad(msg)
    ctx.subjects.need_meta(str(subject))  # unknown -> bad_request
    if (subject in ctx.archived()) != archive:
        kind = ARCHIVE if archive else UNARCHIVE
        event = subject_event(kind, str(subject), dev=ctx.device, at=ctx.clock())
        ctx.log.append([event])
    return {"subject": subject, "archived": archive}


def subject_archive(body: dict[str, Any], ctx: Context) -> dict[str, Any]:
    """``{"subject"}``: hide it everywhere and unlearn it (undo: unarchive)."""
    return _toggle(body, ctx, archive=True)


def subject_unarchive(body: dict[str, Any], ctx: Context) -> dict[str, Any]:
    """``{"subject"}``: bring an archived subject back with its state."""
    return _toggle(body, ctx, archive=False)


ACTIONS: Final = {"archive": subject_archive, "unarchive": subject_unarchive}


def main(argv: list[str], make: Callable[[Path], Context] = Context) -> int:
    """CLI: ``subject archive|unarchive ID [--data DIR]``; 2 when refused."""
    parser = argparse.ArgumentParser(
        prog="python -m tutor subject", description=__doc__
    )
    parser.add_argument("action", choices=sorted(ACTIONS))
    parser.add_argument("subject")
    parser.add_argument("--data", type=Path, default=None, help="data dir")
    args = parser.parse_args(argv)
    ctx = make(args.data or data_dir())
    try:
        out = ACTIONS[args.action]({"subject": args.subject}, ctx)
    except RequestError as err:
        _logger.warning("subject %s refused: %s", args.action, err.message)
        sys.stdout.write(f"refused: {err.message}\n")
        return 2
    sys.stdout.write(json.dumps(out) + "\n")  # the CLI's answer
    return 0
