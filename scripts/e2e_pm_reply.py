#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Flow F32's canned post-mortem answer, shaped by ``tutor/postmortem/prompt.py``.

The fixture's unit is the real ``prefix-sums`` module of the LeetCode subject
with four of kuhy's real solves (their mirrored code copied read-only).
``sum-of-variable-length-subarrays`` is the one one-shot, so the card it
used (:data:`KEPT`) is the kept card: the answer asks to EDIT it anyway, and
F32 asserts code kept it byte-unchanged. It also edits one taught card
(:data:`EDITED`), suspends one (:data:`SUSPENDED`), adds one card and
proposes cards for two future modules plus a skills diff.
"""

from __future__ import annotations

from typing import Any, Final

SLUGS: Final = (
    "running-sum-of-1d-array",
    "find-the-highest-altitude",
    "sum-of-variable-length-subarrays",
    "find-the-pivot-integer",
)
ONE_SHOT: Final = "sum-of-variable-length-subarrays"
KEPT: Final = "prefix-sum-definition"
EDITED: Final = "prefix-sum-recurrence"
SUSPENDED: Final = "histogram-prefix-sorted-position"
NEW_FRONT: Final = "Why does a prefix array start with a 0 before the first element?"
NEW_BACK: Final = "So the sum of a range that starts at index 0 is still P[r+1] - P[l]."
FUTURE: Final = ("stack-queue", "binary-search")
FIX: Final = "Show the leading 0 of every scan before its loop"
KEEP_OPENING: Final = "What does P[i] hold for [3, 1, 4]?"
SKILLS: Final = "- /leetcode: ask for the identity element before any loop"


def _problem(slug: str, used: list[str], finding: str) -> dict[str, Any]:
    return {
        "slug": slug,
        "used": used,
        "skipped": [],
        "instead": "" if slug == ONE_SHOT else "patched the first submission",
        "finding": finding,
    }


def _card(cid: str, verdict: str, front: str = "", back: str = "") -> dict[str, Any]:
    return {
        "id": cid,
        "verdict": verdict,
        "front": front,
        "back": back,
        "finding": f"e2e verdict {verdict}",
    }


def reply() -> dict[str, Any]:
    """The answer the scripted draft tier returns once."""
    return {
        "problems": [
            _problem(SLUGS[0], [KEPT, EDITED], "one wrong type before Accepted"),
            _problem(SLUGS[1], [EDITED], "off by one on the start altitude"),
            _problem(ONE_SHOT, [KEPT], "clean one-shot"),
            _problem(SLUGS[3], [EDITED], "missed the leading 0"),
        ],
        "cards": [
            _card(KEPT, "edit", "Rewrite me?", "The model asked; code keeps me."),
            _card(
                EDITED,
                "edit",
                "How do you get P[i+1] from P[i] and nums[i]?",
                "Add nums[i] to P[i]; P[0] is 0, so the loop starts at i = 0.",
            ),
            _card(SUSPENDED, "suspend"),
        ],
        "new_cards": [
            {"front": NEW_FRONT, "back": NEW_BACK, "why": "pivot", "slugs": [SLUGS[3]]}
        ],
        "lessons": {
            "fix": [{"pattern": FIX, "why": "two solves missed it"}],
            "keep": [
                {
                    "card": KEPT,
                    "opening": KEEP_OPENING,
                    "toy": "[3, 1, 4]",
                    "words": 24,
                    "why": "the one-shot used it",
                }
            ],
        },
        "future": [
            {
                "module": FUTURE[0],
                "cards": [
                    {
                        "front": "What does an empty stack mean when a closer arrives?",
                        "back": (
                            "There is no opener to match, so the string is invalid."
                        ),
                        "why": FIX,
                    }
                ],
            },
            {
                "module": FUTURE[1],
                "cards": [
                    {
                        "front": "What do lo and hi hold before the first probe?",
                        "back": "The first and last index the answer may still be at.",
                        "why": FIX,
                    }
                ],
            },
        ],
        "skills_md": SKILLS,
    }
