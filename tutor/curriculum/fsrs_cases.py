# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The golden fold cases ``fsrs_vectors`` renders into ``contract/fsrs_vectors.json``.

Each case: events as ``(kind, card, offset_ms, device, extra)`` from
:data:`T0`, and the card revs. ``"of": i`` in ``extra`` names event i's eid.
"""

from __future__ import annotations

from typing import Any, Final

T0: Final = 1_791_800_000_000  # 2026-10-12, a fixed start
H: Final = 3_600_000
D: Final = 24 * H
A, B = "dev-a", "dev-b"  # phones
W = "dev-pc"  # the worker: writes every taught/untaught (and, before `src`, drills)
# name -> (events as (kind, card, offset_ms, device, extra), card revs)
Spec = tuple[list[tuple[str, str, int, str, dict[str, Any]]], dict[str, int]]
CASES: Final[dict[str, Spec]] = {
    "taught only": ([("taught", "x", 0, W, {})], {"x": 1}),
    "good after 3 days": (
        [("taught", "x", 0, W, {}), ("review", "x", 3 * D, A, {"r": 3})],
        {"x": 1},
    ),
    "again after 1 day": (
        [("taught", "x", 0, W, {}), ("review", "x", D, A, {"r": 1})],
        {"x": 1},
    ),
    "hard after 2 days": (
        [("taught", "x", 0, W, {}), ("review", "x", 2 * D, B, {"r": 2})],
        {"x": 1},
    ),
    "easy after 5 days": (
        [("taught", "x", 0, W, {}), ("review", "x", 5 * D, A, {"r": 4})],
        {"x": 1},
    ),
    "chain good good again good": (
        [
            ("taught", "x", 0, W, {}),
            ("review", "x", 2 * D, A, {"r": 3}),
            ("review", "x", 9 * D, B, {"r": 3}),
            ("review", "x", 29 * D, A, {"r": 1}),
            ("review", "x", 30 * D, A, {"r": 3}),
        ],
        {"x": 1},
    ),
    "cross-device within 60 s: second dropped": (
        [
            ("taught", "x", 0, W, {}),
            ("review", "x", D, A, {"r": 3}),
            ("review", "x", D + 30_000, B, {"r": 1}),
        ],
        {"x": 1},
    ),
    "cross-device exactly 60 s apart: both kept": (
        [
            ("taught", "x", 0, W, {}),
            ("review", "x", D, A, {"r": 3}),
            ("review", "x", D + 60_000, B, {"r": 1}),
        ],
        {"x": 1},
    ),
    "same device within 60 s: both kept": (
        [
            ("taught", "x", 0, W, {}),
            ("review", "x", D, A, {"r": 1}),
            ("review", "x", D + 10_000, A, {"r": 3}),
        ],
        {"x": 1},
    ),
    "untaught clears, later review ignored": (
        [
            ("taught", "x", 0, W, {}),
            ("review", "x", D, A, {"r": 3}),
            ("untaught", "x", 2 * D, W, {}),
            ("review", "x", 3 * D, B, {"r": 3}),
        ],
        {"x": 1},
    ),
    "review of a never-taught card ignored": (
        [("review", "x", D, A, {"r": 3})],
        {"x": 1},
    ),
    "flag on the current rev": (
        [("taught", "x", 0, W, {}), ("flag", "x", H, B, {"rev": 1, "reason": "wrong"})],
        {"x": 1},
    ),
    "flag cleared by an edit (rev bump)": (
        [("taught", "x", 0, W, {}), ("flag", "x", H, B, {"rev": 1, "reason": "wrong"})],
        {"x": 2},
    ),
    "second taught resets FSRS": (
        [
            ("taught", "x", 0, W, {}),
            ("review", "x", 3 * D, A, {"r": 4}),
            ("taught", "x", 10 * D, W, {}),
        ],
        {"x": 1},
    ),
    "good needs 20 h: 19 h is not": (
        [("taught", "x", 0, W, {}), ("review", "x", 19 * H, A, {"r": 3})],
        {"x": 1},
    ),
    "good at exactly 20 h; two cards": (
        [
            ("taught", "x", 0, W, {}),
            ("review", "x", 20 * H, A, {"r": 3}),
            ("taught", "y", H, W, {}),
            ("review", "y", 30 * H, B, {"r": 2}),
        ],
        {"x": 1, "y": 1},
    ),
    "reviewed: Good 1 h after taught, no gap (not good)": (
        [("taught", "x", 0, W, {}), ("review", "x", H, B, {"r": 3})],
        {"x": 1},
    ),
    "reviewed survives a later Again; Hard alone is not": (
        [
            ("taught", "x", 0, W, {}),
            ("review", "x", H, A, {"r": 4}),
            ("review", "x", 2 * H, A, {"r": 1}),
            ("taught", "y", 0, W, {}),
            ("review", "y", H, B, {"r": 2}),
        ],
        {"x": 1, "y": 1},
    ),
    "re-taught clears reviewed": (
        [
            ("taught", "x", 0, W, {}),
            ("review", "x", H, A, {"r": 3}),
            ("taught", "x", 2 * H, W, {}),
        ],
        {"x": 1},
    ),
    "drill Good (src) 20 h on: scheduled and good, not reviewed": (
        [
            ("taught", "x", 0, W, {}),
            ("review", "x", 20 * H, A, {"r": 3, "src": "drill"}),
        ],
        {"x": 1},
    ),
    "old drill pick (no src, the worker's dev): not reviewed": (
        [("taught", "x", 0, W, {}), ("review", "x", D, W, {"r": 4})],
        {"x": 1},
    ),
    "drill Good, then an app Good: reviewed": (
        [
            ("taught", "x", 0, W, {}),
            ("review", "x", H, W, {"r": 3, "src": "drill"}),
            ("review", "x", 2 * H, A, {"r": 3}),
        ],
        {"x": 1},
    ),
    # ``"of": i`` names event i's eid (the Review's Back takes a rating back).
    "review then undo then re-rate: only the re-rate counts": (
        [
            ("taught", "x", 0, W, {}),
            ("review", "x", 3 * D, A, {"r": 3}),
            ("review_undo", "x", 3 * D + 5_000, A, {"of": 1}),
            ("review", "x", 3 * D + 9_000, B, {"r": 1}),
        ],
        {"x": 1},
    ),
    "undo of an unknown eid: no-op": (
        [
            ("taught", "x", 0, W, {}),
            ("review", "x", 3 * D, A, {"r": 3}),
            (
                "review_undo",
                "x",
                3 * D + 5_000,
                A,
                {"of": "01M4RBCX52MMHCK7K73E6KV999"},
            ),
        ],
        {"x": 1},
    ),
    "unknown src is no drill: reviewed": (
        [
            ("taught", "x", 0, W, {}),
            ("review", "x", H, A, {"r": 3, "src": "elsewhere"}),
        ],
        {"x": 1},
    ),
}
