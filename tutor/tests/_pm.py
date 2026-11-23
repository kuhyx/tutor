# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Post-mortem test helpers: guard files (C6 rows, history, attempts), a unit."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import earned_time

from tutor.postmortem import files
from tutor.rework_context import guard_dir
from tutor.tests._cur import card, module, subject, taught
from tutor.tests._phase import grant
from tutor.tests.conftest import KEY

if TYPE_CHECKING:
    from tutor.curriculum.context import Context

LC = "leetcode-easy-algorithms-in-typescript"
UNIT = "prefix-sums"
AT = 1_800_000_000.0  # the guard's row (seconds)


def guard_row(
    kind: str = files.FINISH_KIND,
    solves: list[str] | None = None,
    *,
    unit: str = UNIT,
    n: int = 1,
    at: float = AT,
    modules: list[str] | None = None,
) -> dict[str, Any]:
    """A C6 row the guard signed."""
    row: dict[str, Any] = {
        "kind": kind,
        "entry_id": f"finish:{unit}:{n}",
        "day": "2027-01-15",
        "detail": {
            "unit": unit,
            "subject": LC,
            "modules": modules or ["a"],
            "at": at,
            "solves": solves if solves is not None else ["p1", "p2", "p3"],
        },
    }
    row["hmac"] = str(earned_time.entry_signature(row, KEY))
    return row


def write_rows(path_kind: str, *rows: dict[str, Any]) -> None:
    """The guard's envelope (``finish`` or ``preview``) holding ``rows``."""
    path = files.finish_path() if path_kind == "finish" else files.preview_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"version": 1, "entries": list(rows)}), "utf-8")


def history(slug: str, *subs: tuple[str, int, str]) -> None:
    """``history/<slug>.json`` with (status, timestamp, code) rows."""
    folder = guard_dir() / "history"
    folder.mkdir(parents=True, exist_ok=True)
    rows = [
        {"id": str(i), "status": st, "timestamp": ts, "code": code}
        for i, (st, ts, code) in enumerate(subs)
    ]
    (folder / f"{slug}.json").write_text(json.dumps({"submissions": rows}), "utf-8")


def attempts(slug: str, beats: list[int]) -> None:
    """``attempts.json`` with one record of ``beats`` on ``slug``."""
    path = guard_dir() / "attempts.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "day": "2027-01-15",
        "slug": slug,
        "beats": [[b, "description"] for b in beats],
    }
    path.write_text(json.dumps({"records": {"k": rec}}), "utf-8")


def unit_subject(ctx: Context, *, teach: bool = True) -> None:
    """LC with module ``a`` (cards a0..a3, taught when ``teach``) and future ``b``."""
    found = {f"a{i}": card("a", i) for i in range(4)}
    found |= {"b0": card("b", 0)}
    mods = [module("a", status="ready", cards=4), module("b", "a", cards=1)]
    subject(ctx, LC, modules=mods, found=found)
    grant((LC, "a"))
    if teach:
        for i in range(4):
            taught(ctx, LC, f"a{i}", ctx.clock(), eid_n=i)


def reply(**over: Any) -> dict[str, Any]:
    """A model answer naming p1..p3 and cards a0..a3."""
    base: dict[str, Any] = {
        "problems": [
            {
                "slug": "p1",
                "used": ["a0", "zz"],
                "skipped": [],
                "instead": "",
                "finding": "clean",
            },
            {
                "slug": "p2",
                "used": ["a1"],
                "skipped": ["a2"],
                "instead": "brute force",
                "finding": "missed a2",
            },
        ],
        "cards": [
            {
                "id": "a0",
                "verdict": "edit",
                "front": "New?",
                "back": "New.",
                "finding": "worked",
            },
            {
                "id": "a1",
                "verdict": "edit",
                "front": "Better a1?",
                "back": "Yes.",
                "finding": "vague",
            },
            {
                "id": "a2",
                "verdict": "suspend",
                "front": "",
                "back": "",
                "finding": "misleading",
            },
            {
                "id": "a3",
                "verdict": "edit",
                "front": "",
                "back": "",
                "finding": "no text",
            },
        ],
        "new_cards": [
            {
                "front": "When does a prefix sum need a 0 sentinel?",
                "back": "When a range starts at index 0.",
                "why": "p2",
                "slugs": ["p2"],
            },
            {"front": "", "back": "dropped", "why": "", "slugs": []},
        ],
        "lessons": {
            "fix": [
                {"pattern": "Teach the sentinel", "why": "p2"},
                {"pattern": "", "why": "x"},
            ],
            "keep": [
                {
                    "card": "a0",
                    "opening": "What sums a range?",
                    "toy": "[1,2,3]",
                    "words": 20,
                    "why": "p1",
                },
                {
                    "card": "a2",
                    "opening": "x",
                    "toy": "y",
                    "words": 3,
                    "why": "not kept",
                },
            ],
        },
        "future": [
            {
                "module": "b",
                "cards": [{"front": "B?", "back": "B.", "why": "sentinel"}],
            },
            {"module": "zz", "cards": []},
        ],
        "skills_md": "- add a sentinel step",
    }
    return base | over
