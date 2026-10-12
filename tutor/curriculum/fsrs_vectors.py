# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Golden vectors for the fold + FSRS: ``contract/fsrs_vectors.json``.

The Dart fold (a port of py-fsrs 6.3.2's Scheduler) must reproduce every
case: per card ``taught``, ``due`` (ms, exact), ``stability`` and
``difficulty`` (1e-6), ``state``, ``flagged`` and ``good`` (§6), plus which
review eids the fold ``dropped`` (cross-device duplicates) or ``ignored``
(card untaught). Regenerate with ``python -m tutor.curriculum.fsrs_vectors``;
a test fails when the file and this generator disagree.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Final

from tutor.curriculum.fold import fold
from tutor.curriculum.ids import ulid
from tutor.curriculum.rules import good

OUT: Final = Path(
    os.environ.get("TUTOR_VECTORS_OUT")
    or Path(__file__).resolve().parents[2] / "contract" / "fsrs_vectors.json"
)
T0: Final = 1_791_800_000_000  # 2026-10-12, a fixed start
H: Final = 3_600_000
D: Final = 24 * H
A, B = "dev-a", "dev-b"
# name -> (events as (kind, card, offset_ms, device, extra), card revs)
Spec = tuple[list[tuple[str, str, int, str, dict[str, Any]]], dict[str, int]]
CASES: Final[dict[str, Spec]] = {
    "taught only": ([("taught", "x", 0, A, {})], {"x": 1}),
    "good after 3 days": (
        [("taught", "x", 0, A, {}), ("review", "x", 3 * D, A, {"r": 3})],
        {"x": 1},
    ),
    "again after 1 day": (
        [("taught", "x", 0, A, {}), ("review", "x", D, A, {"r": 1})],
        {"x": 1},
    ),
    "hard after 2 days": (
        [("taught", "x", 0, A, {}), ("review", "x", 2 * D, B, {"r": 2})],
        {"x": 1},
    ),
    "easy after 5 days": (
        [("taught", "x", 0, A, {}), ("review", "x", 5 * D, A, {"r": 4})],
        {"x": 1},
    ),
    "chain good good again good": (
        [
            ("taught", "x", 0, A, {}),
            ("review", "x", 2 * D, A, {"r": 3}),
            ("review", "x", 9 * D, B, {"r": 3}),
            ("review", "x", 29 * D, A, {"r": 1}),
            ("review", "x", 30 * D, A, {"r": 3}),
        ],
        {"x": 1},
    ),
    "cross-device within 60 s: second dropped": (
        [
            ("taught", "x", 0, A, {}),
            ("review", "x", D, A, {"r": 3}),
            ("review", "x", D + 30_000, B, {"r": 1}),
        ],
        {"x": 1},
    ),
    "cross-device exactly 60 s apart: both kept": (
        [
            ("taught", "x", 0, A, {}),
            ("review", "x", D, A, {"r": 3}),
            ("review", "x", D + 60_000, B, {"r": 1}),
        ],
        {"x": 1},
    ),
    "same device within 60 s: both kept": (
        [
            ("taught", "x", 0, A, {}),
            ("review", "x", D, A, {"r": 1}),
            ("review", "x", D + 10_000, A, {"r": 3}),
        ],
        {"x": 1},
    ),
    "untaught clears, later review ignored": (
        [
            ("taught", "x", 0, A, {}),
            ("review", "x", D, A, {"r": 3}),
            ("untaught", "x", 2 * D, A, {}),
            ("review", "x", 3 * D, B, {"r": 3}),
        ],
        {"x": 1},
    ),
    "review of a never-taught card ignored": (
        [("review", "x", D, A, {"r": 3})],
        {"x": 1},
    ),
    "flag on the current rev": (
        [("taught", "x", 0, A, {}), ("flag", "x", H, B, {"rev": 1, "reason": "wrong"})],
        {"x": 1},
    ),
    "flag cleared by an edit (rev bump)": (
        [("taught", "x", 0, A, {}), ("flag", "x", H, B, {"rev": 1, "reason": "wrong"})],
        {"x": 2},
    ),
    "second taught resets FSRS": (
        [
            ("taught", "x", 0, A, {}),
            ("review", "x", 3 * D, A, {"r": 4}),
            ("taught", "x", 10 * D, A, {}),
        ],
        {"x": 1},
    ),
    "good needs 20 h: 19 h is not": (
        [("taught", "x", 0, A, {}), ("review", "x", 19 * H, A, {"r": 3})],
        {"x": 1},
    ),
    "good at exactly 20 h; two cards": (
        [
            ("taught", "x", 0, A, {}),
            ("review", "x", 20 * H, A, {"r": 3}),
            ("taught", "y", H, B, {}),
            ("review", "y", 30 * H, B, {"r": 2}),
        ],
        {"x": 1, "y": 1},
    ),
}


def _events(name: str, spec: Spec) -> list[dict[str, Any]]:
    out = []
    for i, (kind, card, offset, dev, extra) in enumerate(spec[0]):
        seed = hashlib.sha256(f"{name}/{i}".encode()).digest()
        at = T0 + offset
        out.append(
            {
                "dev": dev,
                "eid": ulid(at, seed),
                "k": kind,
                "s": "car",
                "c": card,
                "at": at,
                **({"rev": 1} if kind == "review" else {}),
                **extra,
            }
        )
    return out


def case(name: str, spec: Spec) -> dict[str, Any]:
    """One vector: its events, card revs and the fold's expected result."""
    events = _events(name, spec)
    folded = fold(events)
    expect = {}
    for card, rev in spec[1].items():
        state = folded.card("car", card)
        memory = state.fsrs_state() or {}
        expect[card] = {
            "taught": state.taught,
            "due": memory.get("due"),
            "stability": memory.get("stability"),
            "difficulty": memory.get("difficulty"),
            "state": memory.get("state"),
            "flagged": state.flagged(rev),
            "good": good(state),
        }
    return {
        "name": name,
        "events": list(reversed(events)),  # unsorted on purpose: the fold sorts
        "cards": {card: {"rev": rev} for card, rev in spec[1].items()},
        "expect": expect,
        "dropped": folded.dropped,
        "ignored": folded.ignored,
    }


def build() -> list[dict[str, Any]]:
    """Every case."""
    return [case(name, spec) for name, spec in CASES.items()]


def render() -> str:
    """The file's text."""
    return json.dumps(build(), indent=1) + "\n"


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(), encoding="utf-8")
    sys.stdout.write(f"wrote {len(CASES)} cases to {OUT}\n")
