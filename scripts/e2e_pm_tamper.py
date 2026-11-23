#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Flow F32's tamper and failure phases: C4 (case ``c4``) and C5 (case ``c5``).

C4: an edited or deleted C6 row starts no post-mortem (the tutor ticks BEFORE
any guard poll: the guard re-writes a deleted C6 file by design), and the
restored row does (the control). An edited or deleted C7 row pays no
``theory-redone`` on the poll that finishes the re-pass, and the restored
row does (the control); each round first un-teaches one card, so the unit is
back in THEORY when the re-pass lands. C5: the real draft tier against a
closed port fails once: one warning, no card change, one failure task; later
ticks are silent until ``--retry``. ``run`` is ``e2e_postmortem.Run``.
"""

from __future__ import annotations

import json
import shutil
from typing import TYPE_CHECKING, Final

import e2e_pm_reply as canned

if TYPE_CHECKING:
    from collections.abc import Callable

    from e2e_pm_run import Run
    from e2e_pm_world import Case

LC: Final = "leetcode-easy-algorithms-in-typescript"
REDONE: Final = f"theory-redone:{LC}:prefix-sums:1"
FINISH: Final = "home/.local/share/leetcode_guard/unit_finish.json"
REVISIONS: Final = "home/.local/share/tutor/postmortems/revisions.json"
FAILED: Final = "Post-mortem prefix-sums failed"
RETRY: Final = "python -m tutor postmortem prefix-sums --retry"


def _silent(run: Run, case: Case, label: str) -> None:
    tick = case.tutor("tick", "queue")
    after = case.tutor("facts")
    run.show(f"tick ({label})", tick)
    run.check(
        tick["outcome"] == "idle"
        and tick["model_calls"] == 0
        and not after["revisions"],
        f"{label}: no post-mortem, no model call",
        after,
    )
    run.check(not case.tasks() and not after["failed"], f"{label}: no task, no marker")


def c4_finish(run: Run, case: Case) -> None:
    """Edited, then deleted C6: nothing starts; the restored row runs it."""
    path = case.dir / FINISH
    good = path.read_text("utf-8")
    doc = json.loads(good)
    doc["entries"][0]["detail"]["solves"][0] = "two-sum"
    path.write_text(json.dumps(doc), "utf-8")
    run.show("edited C6 detail", doc["entries"][0]["detail"])
    _silent(run, case, "edited C6 row")
    path.unlink()
    _silent(run, case, "deleted C6 file")
    path.write_text(good, "utf-8")
    case.tutor("queue")
    tick = case.tutor("tick", "queue")
    run.show("tick (restored C6, control)", tick)
    run.check(tick["outcome"] == "done", "control: the untouched row runs it")
    shutil.copyfile(case.dir / REVISIONS, case.dir / "revisions.good.json")


def _round(run: Run, case: Case, label: str, change: Callable[[], None]) -> None:
    """Back to THEORY, tamper with C7, re-pass, poll: report what minted."""
    case.tutor("untaught", canned.EDITED)
    case.guard("harvest")
    detail = case.json("home/.local/share/leetcode_guard/theory_phase.json") or {}
    run.show("C3 before the re-pass", detail.get("detail"))
    change()
    run.show("C2 after the re-pass", case.tutor("retake")["c2"][-2:])
    code, out = case.guard("harvest")
    ids = case.ledger_ids("theory-redone:")
    run.show(f"theory-redone ids ({label})", ids)
    want = [REDONE] if label == "control" else []
    run.check(code == 0 and ids == want, f"{label}: theory-redone {want}", out[-600:])
    tick = case.tutor("tick", "queue")
    run.check(
        tick["outcome"] == "idle" and tick["model_calls"] == 0,
        f"{label}: no second post-mortem",
        tick,
    )


def c4_rev_edit(run: Run, case: Case) -> None:
    """A hand-edited C7 row pays nothing."""

    def edit() -> None:
        path = case.dir / REVISIONS
        doc = json.loads(path.read_text("utf-8"))
        doc["entries"][0]["detail"]["at"] = 0
        path.write_text(json.dumps(doc), "utf-8")
        run.show("edited C7 detail", doc["entries"][0]["detail"])

    _round(run, case, "edited C7", edit)


def c4_rev_delete(run: Run, case: Case) -> None:
    """A deleted C7 file pays nothing."""
    _round(run, case, "deleted C7", (case.dir / REVISIONS).unlink)


def c4_rev_control(run: Run, case: Case) -> None:
    """The untouched C7 row pays once: the two refusals were not vacuous."""

    def restore() -> None:
        shutil.copyfile(case.dir / "revisions.good.json", case.dir / REVISIONS)

    _round(run, case, "control", restore)


def c5_fail(run: Run, case: Case) -> None:
    """The model is down: one warning, nothing changed, one failure task."""
    base = json.loads((case.dir / "baseline.json").read_text("utf-8"))
    tick = case.tutor("tick", "down", model_down=True)
    run.show("tick (model down)", tick)
    mine = [w for w in tick["warnings"] if w.startswith("tutor.postmortem")]
    run.check(tick["outcome"] == "failed", "tick: failed")
    run.check(len(mine) == 1, "one post-mortem warning", mine)
    after = case.tutor("facts")
    same = all(after["cards"][c]["sha"] == v["sha"] for c, v in base["cards"].items())
    run.check(same and set(after["cards"]) == set(base["cards"]), "no card change")
    run.check(
        after["c2"] == base["c2"] and not after["c7"] and not after["revisions"],
        "no C2 flip, no C7 row, no report",
        after,
    )
    run.show("failed markers", after["failed"])
    tasks = case.tasks()
    run.show("tasks", tasks)
    run.check(
        len(tasks) == 1 and tasks[0]["title"] == FAILED and RETRY in tasks[0]["body"],
        f"exactly one task {FAILED!r} holding {RETRY!r}",
    )
    again = case.tutor("tick", "queue")
    run.show("later tick", again)
    run.check(
        again["outcome"] == "idle" and again["model_calls"] == 0,
        "later tick: no model call",
    )
    run.check(len(case.tasks()) == 1, "later tick: files nothing")


def c5_retry(run: Run, case: Case) -> None:
    """``--retry`` clears the marker; the next tick performs the post-mortem."""
    run.show("retry", case.retry())
    run.check(not case.tutor("facts")["failed"], "the failed marker is gone")
    case.tutor("queue")
    tick = case.tutor("tick", "queue")
    run.show("tick after retry", tick)
    after = case.tutor("facts")
    run.check(
        tick["outcome"] == "done" and after["revisions"] == 1, "the post-mortem ran"
    )
    run.show("task titles", [t["title"] for t in case.tasks()])


TAMPER: Final[dict[str, Callable[[Run, Case], None]]] = {
    "c4-finish": c4_finish,
    "c4-rev-edit": c4_rev_edit,
    "c4-rev-delete": c4_rev_delete,
    "c4-rev-control": c4_rev_control,
    "c5-fail": c5_fail,
    "c5-retry": c5_retry,
}
