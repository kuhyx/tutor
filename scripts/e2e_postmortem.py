#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Agent E2E flow F32: a finished unit's post-mortem, across tutor and guard.

The real ``watch.tick`` (the body of the worker's ``PostmortemWork``) runs
in-process against a scratch tutor data dir; the guard's real harvester,
``--status`` and first lock run (its own ``scripts.e2e_theory_roles``) run
against a scratch guard dir under the same scratch ``$HOME`` and key. The
draft tier is a queue holding one canned answer (``e2e_pm_reply``) or, for
C5, the real ``ask_draft`` against a closed port; todo tasks go to a FAKE
MCP server. Not the sandbox worker: ``up --scripted`` scripts tutor turns,
not the draft tier, and its worker would race the driver (DOCS-e2e-learn.md).

One phase per call, each under 40 s, exit 0 = PASS (``DOCS-e2e-learn.md``)::

    setup CASE | finish CASE      # fixture, then the guard writes C6 (main|c4|c5)
    c2 | c3 | c6 | c7              # case main, in this order
    c4-finish | c4-rev-edit | c4-rev-delete | c4-rev-control   # case c4
    c5-fail | c5-retry             # case c5
    down                           # stop the fake servers, delete $E2E_PM_DIR
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from typing import Any, Final

import e2e_pm_reply as canned
from e2e_pm_run import Run
from e2e_pm_seed import copy_history, seed
from e2e_pm_tamper import TAMPER
from e2e_pm_world import BASE, LIVE_TUTOR, PAST, SYSTEMCTL, UNIT_PREFIX, Case

LC: Final = "leetcode-easy-algorithms-in-typescript"
REDONE: Final = f"theory-redone:{LC}:prefix-sums:1"
APPLY: Final = "Apply post-mortem prefix-sums: future modules + skills"
MARK: Final = ".e2e-postmortem"


def setup(run: Run, case: Case) -> None:
    """Fresh case: tutor fixture (taught at PAST), scratch pool, seeded ledger."""
    BASE.mkdir(parents=True, exist_ok=True)
    (BASE / MARK).touch()
    case.create()
    fixture = case.tutor("fixture", str(LIVE_TUTOR), str(PAST))
    run.show("tutor fixture", {k: fixture[k] for k in ("taught", "c2")})
    run.check(fixture["c2"] and fixture["c2"][-1][0] is True, "C2 done:true at PAST")
    code, out = case.guard("pool")
    run.check(code == 0, "guard scratch pool written", out[-500:])
    seeded = seed(case)
    run.check("seeded a new ledger" in seeded, "guard's first lock run seeded", seeded)


def finish(run: Run, case: Case) -> None:
    """The guard harvests the four solves; its poll writes the C6 row."""
    code, out = case.guard("harvest", ac=",".join(canned.SLUGS))
    run.show("harvest", out.strip().splitlines()[:3])
    run.check(code == 0 and "credited 4" in out, "guard credited the 4 solves", out)
    doc = case.json("home/.local/share/leetcode_guard/unit_finish.json") or {}
    rows: list[Any] = doc.get("entries") or []
    run.show("C6 rows", rows)
    want = sorted(canned.SLUGS)
    run.check(
        len(rows) == 1 and rows[0]["detail"]["solves"] == want and rows[0].get("hmac"),
        "one signed C6 row from record_finishes, claiming the 4 solves",
        rows,
    )
    phase = case.json("home/.local/share/leetcode_guard/theory_phase.json") or {}
    run.show("C3 after the finish", phase.get("detail"))
    run.show("histories copied", copy_history(case))
    (case.dir / "baseline.json").write_text(json.dumps(case.tutor("facts")), "utf-8")


def _phase(case: Case) -> dict[str, Any]:
    doc = case.json("home/.local/share/leetcode_guard/theory_phase.json") or {}
    return dict(doc.get("detail") or {})


def c2(run: Run, case: Case) -> None:
    """The tick runs the post-mortem; the guard sends the unit back to THEORY."""
    base = json.loads((case.dir / "baseline.json").read_text("utf-8"))
    run.show("queue", case.tutor("queue"))
    tick = case.tutor("tick", "queue")
    run.show("tick", tick)
    run.check(
        tick["outcome"] == "done" and tick["model_calls"] == 1, "tick: done, 1 call"
    )
    after = case.tutor("facts")
    report = case.json(f"home/.local/share/tutor/postmortems/{LC}/prefix-sums.json")
    applied = report["revisions"][-1]["applied"] if report else {}
    run.show("applied", applied)
    run.check(
        report and report.get("hmac"),
        "signed report postmortems/<subject>/prefix-sums.json",
    )
    new = sorted(set(after["cards"]) - set(base["cards"]))
    run.show("new cards", {c: after["cards"][c]["front"] for c in new})
    run.check(
        new and new == applied.get("added"), "the module gained the new card", new
    )
    edited = after["cards"][canned.EDITED]
    run.show("edited card", edited)
    run.check(
        edited["rev"] > base["cards"][canned.EDITED]["rev"] and not edited["taught"],
        "the edited taught card is untaught (rev bumped)",
    )
    kept = (base["cards"][canned.KEPT]["sha"], after["cards"][canned.KEPT]["sha"])
    run.check(
        kept[0] == kept[1],
        f"kept card {canned.KEPT} byte-unchanged (model said edit)",
        kept,
    )
    run.check(after["cards"][canned.SUSPENDED]["suspended"], "suspended card suspended")
    run.show("C2 prefix-sums rows", after["c2"])
    run.check(
        [r[0] for r in after["c2"]] == [True, False], "a signed done:false row landed"
    )
    run.show("C7", after["c7"])
    run.check(len(after["c7"] or []) == 1, "one signed C7 row")
    code, out = case.guard("harvest")
    detail = _phase(case)
    run.show("C3 after the guard's poll", detail)
    run.check(
        code == 0
        and detail.get("phase") == "theory"
        and detail.get("unit") == "prefix-sums",
        "guard poll_theory: prefix-sums back in THEORY",
        out[-800:],
    )
    code, out = case.guard("status")
    lines = [
        ln for ln in out.splitlines() if ln.startswith(("unit ", "theory ", "learn "))
    ]
    run.show("--status lines", lines)
    run.check(
        code == 0 and "unit       prefix-sums -- theory" in out,
        "--status: prefix-sums theory",
    )
    live = [c for c in after["cards"].values() if not c["suspended"]]
    want = (sum(c["taught"] for c in live), len(live))
    code, out = case.guard("unit")
    shown = json.loads(out.strip().splitlines()[-1]) if code == 0 else {}
    run.show("guard unit dict (MCP/snapshot)", shown)
    got = (shown.get("cards_taught"), shown.get("cards_total"))
    run.check(
        shown.get("phase") == "theory" and got == want,
        f"guard shows {want[1] - want[0]} untaught of {want[1]} cards",
        (got, want, out[-800:]),
    )


def c3(run: Run, case: Case) -> None:
    """The re-pass pays theory-redone once; repeats mint and run nothing."""
    retake = case.tutor("retake")
    run.show("retaught", retake["retaught"])
    run.show("C2 rows", retake["c2"])
    run.check(retake["c2"][-1][0] is True, "reconcile signed done:true again")
    code, out = case.guard("harvest")
    ids = case.ledger_ids("theory-redone:")
    run.show("theory-redone ids", ids)
    run.check(code == 0 and ids == [REDONE], f"exactly one {REDONE}", out[-800:])
    case.guard("harvest")
    run.check(
        case.ledger_ids("theory-redone:") == [REDONE], "a second poll mints nothing"
    )
    before = len(case.tasks())
    tick = case.tutor("tick", "queue")
    run.show("second tick", tick)
    run.check(
        tick["outcome"] == "idle" and tick["model_calls"] == 0,
        "second tick: idle, no model call",
    )
    run.check(len(case.tasks()) == before, "no new todo task")


def c6(run: Run, case: Case) -> None:
    """The FAKE MCP got the approval task with the cards and the skills."""
    tasks = [t for t in case.tasks() if t["title"] == APPLY]
    run.show("all task titles", [t["title"] for t in case.tasks()])
    run.check(len(tasks) == 1, f"one task {APPLY!r}", case.tasks())
    task = tasks[0] if tasks else {"body": "", "repo": "", "title": ""}
    run.say("  body:\n" + task["body"])
    run.check(
        task["repo"] == "kuhyx/tutor" and not task["title"].startswith("MANUAL"),
        "project tutor, no MANUAL prefix",
    )
    fronts = [c["front"] for f in canned.reply()["future"] for c in f["cards"]]
    body = task["body"]
    run.check(
        all(f"### {m}" in body for m in canned.FUTURE), "a section per future module"
    )
    run.check(all(f in body for f in fronts), "every proposed card listed")
    run.check(
        "## Skills and generation" in body and canned.SKILLS in body,
        "the skills section",
    )


def c7(run: Run, case: Case) -> None:
    """lessons.json is signed and every future draft prompt carries it."""
    found = case.tutor("lessons")
    run.show("lessons text", found["lessons"])
    run.say("  draft prompt tail (stack-queue):\n" + found["prompt_tail"])
    run.check(case.tutor("facts")["lessons"] == 1, "signed lessons.json, one entry")
    tail = found["prompt_tail"]
    run.check(
        canned.FIX in tail and canned.KEEP_OPENING in tail,
        "with_lessons output carries FIX and KEEP",
    )


def down(run: Run) -> None:
    """Stop every fake todo server of this worktree; delete the scratch root."""
    subprocess.run([SYSTEMCTL, "--user", "stop", f"{UNIT_PREFIX}*"], check=False)
    if (BASE / MARK).is_file():
        shutil.rmtree(BASE)
    run.say(f"e2e postmortem down: {BASE} removed")


PHASES: Final = {"c2": c2, "c3": c3, "c6": c6, "c7": c7}


def main(argv: list[str]) -> int:
    """Run one phase; exit 0 only when every check passed."""
    phase = argv[0] if argv else ""
    run = Run(f"{phase}-{argv[1]}" if phase in {"setup", "finish"} else phase)
    if phase == "down":
        down(run)
    elif phase in {"setup", "finish"}:
        (setup if phase == "setup" else finish)(run, Case(argv[1]))
    elif phase in PHASES:
        PHASES[phase](run, Case("main"))
    elif phase in TAMPER:
        TAMPER[phase](run, Case(phase.split("-")[0]))
    else:
        sys.exit(f"usage: {__doc__}")
    return 1 if run.failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
