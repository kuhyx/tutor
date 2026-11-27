# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The fold cases of step 11, the ``unchecked`` mark (``README.md`` "Fallback").

A card read in fallback (or taught by a free model) is taught and marked
``unchecked`` until Claude's ``checked``. Same shape as
:data:`fsrs_cases.CASES`; ``fsrs_vectors`` renders all of them.
"""

from __future__ import annotations

from typing import Final

from tutor.curriculum.fsrs_cases import A, D, H, Spec, W

_READ: Final = {"src": "read"}
CHECK_CASES: Final[dict[str, Spec]] = {
    "unchecked: read mode got it": (
        [("taught", "x", 0, W, {}), ("unchecked", "x", 1, W, _READ)],
        {"x": 1},
    ),
    "unchecked: read mode again (Again 2 ms after taught)": (
        [
            ("taught", "x", 0, W, {}),
            ("unchecked", "x", 1, W, _READ),
            ("review", "x", 2, W, {"r": 1}),
        ],
        {"x": 1},
    ),
    "unchecked: checked clears it": (
        [
            ("taught", "x", 0, W, {}),
            ("unchecked", "x", 1, W, {"src": "free"}),
            ("checked", "x", D, W, {}),
        ],
        {"x": 1},
    ),
    "unchecked: a failed check is Again then checked": (
        [
            ("taught", "x", 0, W, {}),
            ("unchecked", "x", 1, W, _READ),
            ("review", "x", D, W, {"r": 1}),
            ("checked", "x", D + 1, W, {}),
        ],
        {"x": 1},
    ),
    "unchecked: a Claude re-teach clears it": (
        [
            ("taught", "x", 0, W, {}),
            ("unchecked", "x", 1, W, _READ),
            ("taught", "x", D, W, {}),
        ],
        {"x": 1},
    ),
    "unchecked: on an untaught card does nothing": (
        [("unchecked", "x", H, W, _READ)],
        {"x": 1},
    ),
    "unchecked: untaught clears it": (
        [
            ("taught", "x", 0, W, {}),
            ("unchecked", "x", 1, W, _READ),
            ("untaught", "x", H, W, {}),
        ],
        {"x": 1},
    ),
    "unchecked: an app review keeps it": (
        [
            ("taught", "x", 0, W, {}),
            ("unchecked", "x", 1, W, _READ),
            ("review", "x", D, A, {"r": 3}),
        ],
        {"x": 1},
    ),
}
