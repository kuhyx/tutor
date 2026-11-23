#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Flow F32's tutor side: one op per call, run by ``scripts/e2e_postmortem.py``.

The driver starts this with every tutor path pointed into the case's scratch
``$HOME`` (``TUTOR_DATA``, ``TUTOR_KEY``, ``TUTOR_GUARD_DATA``, the caches,
``XDG_STATE_HOME``) and ``TUTOR_TODO_URL`` at the FAKE todo server
(``e2e_pm_todo.py``); :func:`_refuse_live` checks all of it before anything
runs. Ops print one JSON object (the driver's evidence):

- ``fixture SRC PAST``: copy the LeetCode subject from SRC (read-only), an
  empty tutor ledger, and teach every live prefix-sums card at unix ``PAST``
  (worker ``taught`` events), so ``module_state`` signs ``done: true`` then.
- ``queue``: the canned answer (``e2e_pm_reply``), checked against the schema.
- ``tick queue|down``: one real ``watch.tick``; the draft tier is the queue
  (an empty queue raises) or the real ``ask_draft`` against a closed port.
  Every draft call is logged to ``draft_calls.jsonl``.
- ``retake``: teach every untaught live card of the unit (the re-pass).
- ``untaught CARD``: un-teach one card. ``facts``: the state F32 asserts on.
- ``lessons``: the real draft prompt of a future module with the lessons.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import sys
import time
from typing import Any, Final

import e2e_pm_reply as canned
import jsonschema

import tutor
from tutor.curriculum import modelcall
from tutor.curriculum.context import Context
from tutor.curriculum.draft_prompt import prompt as draft_text
from tutor.curriculum.draft_prompt import with_lessons
from tutor.curriculum.errors import MODEL_ERROR, RequestError
from tutor.curriculum.eventlog import worker_event
from tutor.curriculum.plan_context import Scope
from tutor.postmortem import files, lessons, prompt, report, signed, watch

LC: Final = "leetcode-easy-algorithms-in-typescript"
UNIT: Final = "prefix-sums"
CLOSED: Final = "http://127.0.0.1:9"
ROOT: Final = Path(__file__).resolve().parents[1]
type Json = dict[str, Any]


def _refuse_live() -> Path:
    """The case dir; exits unless every path is inside it and todo is the fake."""
    case = Path(os.environ["E2E_PM_CASE"]).resolve()
    names = (
        *("TUTOR_DATA", "TUTOR_KEY", "TUTOR_GUARD_DATA", "TUTOR_SOURCE_CACHE"),
        *("TUTOR_TODO_TOKEN_FILE", "XDG_STATE_HOME", "TUTOR_THEORY_PHASE"),
    )
    for name in names:
        if not Path(os.environ[name]).resolve().is_relative_to(case):
            sys.exit(f"refused: {name} is outside {case}")
    url = os.environ["TUTOR_TODO_URL"]
    if not url.startswith("http://127.0.0.1:") or ":8735" in url:
        sys.exit(f"refused: TUTOR_TODO_URL {url} is not the fake")
    if not Path(tutor.__file__).resolve().is_relative_to(ROOT):
        sys.exit(f"refused: tutor imported from {tutor.__file__}")
    return case


CASE: Final = _refuse_live()
DATA: Final = Path(os.environ["TUTOR_DATA"])
CALLS: Final = CASE / "draft_calls.jsonl"
QUEUE: Final = CASE / "draft_queue.json"


def _record(text: str, mode: str) -> None:
    row = {"at": time.time(), "mode": mode, "chars": len(text)}
    row["slugs"] = [s for s in canned.SLUGS if s in text]
    with CALLS.open("a", encoding="utf-8") as sink:
        sink.write(json.dumps(row) + "\n")


def scripted(_system: str, text: str, schema: Json) -> Json:
    """The draft tier as a queue: pop the next answer, or raise when empty."""
    _record(text, "queue")
    queue = json.loads(QUEUE.read_text(encoding="utf-8")) if QUEUE.is_file() else []
    if not queue:
        raise RequestError(MODEL_ERROR, "e2e: unexpected model call")
    QUEUE.write_text(json.dumps(queue[1:]), encoding="utf-8")
    jsonschema.validate(queue[0], schema)
    return dict(queue[0])


def down(system: str, text: str, schema: Json) -> Json:
    """The real draft tier, only ever against a closed port (an outage)."""
    if os.environ.get("ANTHROPIC_BASE_URL") != CLOSED:
        sys.exit("refused: the real model only runs against the closed port")
    _record(text, "down")
    return modelcall.ask_draft(system, text, schema)


def calls() -> int:
    """Draft calls so far in this case."""
    return len(CALLS.read_text(encoding="utf-8").splitlines()) if CALLS.is_file() else 0


def _module_cards(ctx: Context) -> dict[str, Any]:
    cards = ctx.subjects.cards(LC)
    return {c: r for c, r in cards.items() if r.module == UNIT}


def _teach(ctx: Context, cids: list[str], kind: str = "taught") -> None:
    at = ctx.clock()
    ctx.log.append([worker_event(kind, (LC, c), dev=ctx.device, at=at) for c in cids])


def fixture(src: Path, past: float) -> Json:
    """The case's tutor data: the subject copy, taught in full at ``past``."""
    shutil.copytree(src / "subjects" / LC, DATA / "subjects" / LC)
    (DATA / "ledger.json").write_text('{"version": 1, "entries": []}', "utf-8")
    ctx = Context(DATA, clock=lambda: int(past * 1000))
    live = [c for c, r in _module_cards(ctx).items() if not r.suspended]
    _teach(ctx, live)
    return {"taught": len(live), **facts()}


def tick(mode: str) -> Json:
    """One real worker tick; its outcome and every warning it logged."""
    seen: list[str] = []

    class Keep(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            if record.levelno >= logging.WARNING:
                seen.append(f"{record.name}: {record.getMessage()}")

    logging.getLogger().addHandler(Keep())
    ctx = Context(DATA)
    ctx.draft = scripted if mode == "queue" else down
    before = calls()
    outcome = watch.tick(ctx, time.time())
    return {"outcome": outcome, "model_calls": calls() - before, "warnings": seen}


def retake() -> Json:
    """Teach every untaught live card of the unit, as the re-pass does."""
    ctx = Context(DATA)
    taught = ctx.fold().taught_ids(LC)
    live = [c for c, r in _module_cards(ctx).items() if not r.suspended]
    todo = sorted(c for c in live if c not in taught)
    _teach(ctx, todo)
    return {"retaught": todo, **facts()}


def _digest(raw: object) -> str:
    return hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest()[:16]


def facts() -> Json:
    """The cards, C2 rows, report, C7, markers, tasks and lessons on disk."""
    ctx = Context(DATA)
    raw = json.loads((DATA / "subjects" / LC / "cards.json").read_text("utf-8"))
    taught = ctx.fold().taught_ids(LC)
    rows = signed.verified_rows(DATA / "module_state.json", "module_state") or []
    tasks = files.tasks_dir()
    return {
        "cards": {
            c: {
                "sha": _digest(raw[c]),
                "rev": r.rev,
                "suspended": r.suspended,
                "taught": c in taught,
                "front": r.front,
            }
            for c, r in _module_cards(ctx).items()
        },
        "c2": [
            [r["detail"]["done"], r["detail"]["at"], r["day"]]
            for r in rows
            if r["detail"].get("module") == UNIT
        ],
        "revisions": len(report.revisions(LC, UNIT)),
        "c7": signed.verified_rows(files.revisions_path(), files.REV_KIND),
        "failed": sorted(p.name for p in (files.root() / "failed").glob("*.json")),
        "tasks": sorted(p.name for p in tasks.glob("*.json")) if tasks.is_dir() else [],
        "lessons": len(lessons.entries(LC)),
        "model_calls": calls(),
    }


def lesson_prompt() -> Json:
    """The draft prompt of the first future module, lessons appended."""
    ctx = Context(DATA)
    plan = ctx.subjects.plan(LC)
    module = plan.module(canned.FUTURE[0]) if plan else None
    if plan is None or module is None:
        return {"error": "no plan"}
    scope = Scope(ctx.subjects.need_meta(LC), module, plan)
    text = with_lessons(draft_text(scope, ctx.subjects.cards(LC), []), LC)
    return {"lessons": lessons.text(LC), "prompt_tail": text[-900:], "chars": len(text)}


def main() -> int:
    """Run one op; print its JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("op")
    parser.add_argument("args", nargs="*")
    args = parser.parse_args()
    if args.op == "queue":
        jsonschema.validate(canned.reply(), prompt.SCHEMA)
        QUEUE.write_text(json.dumps([canned.reply()]), encoding="utf-8")
        out: Json = {"queued": 1}
    elif args.op == "fixture":
        out = fixture(Path(args.args[0]), float(args.args[1]))
    elif args.op == "tick":
        out = tick(args.args[0])
    elif args.op == "untaught":
        _teach(Context(DATA), args.args, "untaught")
        out = facts()
    else:
        ops = {"retake": retake, "facts": facts, "lessons": lesson_prompt}
        out = ops[args.op]()
    print(json.dumps(out, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
