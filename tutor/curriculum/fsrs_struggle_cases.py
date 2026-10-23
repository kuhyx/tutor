# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The fold cases of step 7, ``struggle(c)`` (``DOCS-contract-struggle.md`` §3).

Same shape as :data:`fsrs_cases.CASES`; ``fsrs_vectors`` renders both.
"""

from __future__ import annotations

from typing import Final

from tutor.curriculum.fsrs_cases import A, B, D, H, Spec, W

_AGAIN: Final = {"r": 1}
STRUGGLE_CASES: Final[dict[str, Spec]] = {
    "struggle: three Again ratings": (
        [
            ("taught", "x", 0, W, {}),
            ("review", "x", D, A, _AGAIN),
            ("review", "x", 2 * D, B, _AGAIN),
            ("review", "x", 3 * D, A, _AGAIN),
        ],
        {"x": 1},
    ),
    "struggle: Again, Again, Good, Again": (
        [
            ("taught", "x", 0, W, {}),
            ("review", "x", D, A, _AGAIN),
            ("review", "x", 2 * D, A, _AGAIN),
            ("review", "x", 3 * D, A, {"r": 3}),
            ("review", "x", 4 * D, A, _AGAIN),
        ],
        {"x": 1},
    ),
    # The card is at rev 2: the two Again ratings at rev 1 are of the old wording.
    "struggle: Again at an old rev ignored after an edit": (
        [
            ("taught", "x", 0, W, {}),
            ("review", "x", D, A, _AGAIN),
            ("review", "x", 2 * D, A, _AGAIN),
            ("review", "x", 3 * D, B, {"r": 1, "rev": 2}),
        ],
        {"x": 2},
    ),
    "struggle: undo pops the last Again": (
        [
            ("taught", "x", 0, W, {}),
            ("review", "x", D, A, _AGAIN),
            ("review", "x", 2 * D, A, _AGAIN),
            ("review", "x", 3 * D, A, _AGAIN),
            ("review_undo", "x", 3 * D + 5_000, A, {"of": 3}),
        ],
        {"x": 1},
    ),
    "struggle: cross-device Again within 60 s counts once": (
        [
            ("taught", "x", 0, W, {}),
            ("review", "x", D, A, _AGAIN),
            ("review", "x", D + 30_000, B, _AGAIN),
            ("review", "x", 2 * D, B, _AGAIN),
        ],
        {"x": 1},
    ),
    "struggle: re-teach resets": (
        [
            ("taught", "x", 0, W, {}),
            ("review", "x", D, A, _AGAIN),
            ("review", "x", 2 * D, A, _AGAIN),
            ("review", "x", 3 * D, A, _AGAIN),
            ("taught", "x", 3 * D + H, W, {}),
        ],
        {"x": 1},
    ),
    "struggle: drill picks count": (
        [
            ("taught", "x", 0, W, {}),
            ("review", "x", H, A, {"r": 1, "src": "drill"}),
            ("review", "x", D, A, _AGAIN),
        ],
        {"x": 1},
    ),
    "struggle: Hard ends the run": (
        [
            ("taught", "x", 0, W, {}),
            ("review", "x", D, A, _AGAIN),
            ("review", "x", 2 * D, A, {"r": 2}),
        ],
        {"x": 1},
    ),
}
