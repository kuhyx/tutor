#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""F33's checks on the sandbox's files and the page's rects (``e2e_fallback.py``).

Pure helpers, no browser: what read mode wrote to ``log.jsonl``, the read
run's rows in the sandbox ledger, the per-module due counts the server's
fold gives (the sheet and the Plan buttons must show the same), the labels
``Review <title> (N due)`` and ``N left``, and which rects leave the viewport.
"""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
from typing import Any, Final

from e2e_fallback_state import Seeder

AGAIN: Final = 1
READ_PREFIX: Final = "read-"
# find / findAll / text, run in the page (``e2e_cdp.py`` keeps its copy private).
PAGE_JS: Final = Path(__file__).with_name("e2e_page.js").read_text(encoding="utf-8")
_DUE: Final = re.compile(r"^Review (.+) \((\d+) due\)$")
_LEFT: Final = re.compile(r"^(\d+) left$", re.MULTILINE)


def log_events(data: Path) -> list[dict[str, Any]]:
    """Every event of ``<data>/log.jsonl``, in file order."""
    lines = (data / "log.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def read_problems(
    events: list[dict[str, Any]],
    got_it: tuple[str, str],
    again: tuple[str, str],
    since_ms: int,
) -> list[str]:
    """What is missing from the events read mode owes the two rated cards.

    Each card (``(subject, card)``): a ``taught`` and an ``unchecked`` with
    ``src: read`` at or after ``since_ms``; the "again" card a review rated
    1, the "got it" card none.
    """
    problems = []
    for ref, rated_again in ((got_it, False), (again, True)):
        mine = [
            e
            for e in events
            if (e.get("s"), e.get("c")) == ref and int(e.get("at", 0)) >= since_ms
        ]
        kinds = {e["k"] for e in mine}
        if "taught" not in kinds:
            problems.append(f"{ref}: no taught event")
        if not any(e["k"] == "unchecked" and e.get("src") == "read" for e in mine):
            problems.append(f"{ref}: no unchecked event with src read")
        again_reviews = [e for e in mine if e["k"] == "review" and e.get("r") == AGAIN]
        if rated_again and not again_reviews:
            problems.append(f"{ref}: no review rated {AGAIN}")
        if not rated_again and again_reviews:
            problems.append(f"{ref}: rated got it but reviewed Again")
    return problems


def read_rows(data: Path, since: float) -> list[dict[str, Any]]:
    """The ledger's credit rows of a read run created at or after ``since`` (s)."""
    saved = json.loads((data / "ledger.json").read_text(encoding="utf-8"))
    return [
        row
        for row in saved.get("entries", [])
        if row.get("kind") == "credit"
        and str((row.get("detail") or {}).get("session_id", "")).startswith(READ_PREFIX)
        and float(row.get("created_at", 0)) >= since
    ]


def run_active(data: Path) -> float:
    """Shown -> rated seconds of the newest read run (``<data>/read/*.jsonl``).

    Each ``rate`` line pairs with the last ``prompt`` line of its card: the
    gap the run's engagement clock counts (``model_free_pay.Runs.accrue``).
    """
    runs = sorted((data / "read").glob(f"{READ_PREFIX}*.jsonl"))
    if not runs:
        return 0.0
    shown: dict[str, float] = {}
    total = 0.0
    for line in runs[-1].read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        if event.get("type") == "prompt":
            shown[event["card"]] = float(event["logged_at"])
        elif event.get("type") == "rate" and event.get("card") in shown:
            total += float(event["logged_at"]) - shown.pop(event["card"])
    return total


def due_by_module(data: Path, subject: str, now_ms: int) -> dict[str, int]:
    """``subject``'s cards due at ``now_ms`` per module id, by the server's fold."""
    seeder = Seeder(data, subject, now_ms)
    view = seeder.target
    return dict(Counter(view.cards[c].module for c in seeder.due(view, now_ms)))


def module_titles(data: Path, subject: str) -> dict[str, str]:
    """Module id -> title of ``subject``'s plan."""
    view = Seeder(data, subject, 0).target
    return {m.id: m.title for m in view.plan.modules}


def due_labels(labels: list[str]) -> dict[str, int]:
    """``Review <title> (N due)`` labels as title -> N (others ignored)."""
    out = {}
    for label in labels:
        if (hit := _DUE.match(label)) and hit.group(1) != "all":
            out[hit.group(1)] = int(hit.group(2))
    return out


def left_count(text: str) -> int | None:
    """The Review screen's ``N left`` in the page text, if shown."""
    hit = _LEFT.search(text)
    return int(hit.group(1)) if hit else None


def outside(
    rects: list[dict[str, Any]], width: float, height: float
) -> list[dict[str, Any]]:
    """The rects not wholly inside a ``width`` x ``height`` viewport (1 px slack)."""
    return [
        r
        for r in rects
        if r["left"] < -1
        or r["top"] < -1
        or r["right"] > width + 1
        or r["bottom"] > height + 1
    ]
