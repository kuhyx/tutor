# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The palindrome task of a mock: statement, reference answers, examples.

Expected values come from the reference functions below, never from a
model. Visible examples are shown and runnable; hidden ones only count at
``finish``. Everything runs through ``code_runner`` (bubblewrap).
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import TYPE_CHECKING, Any, Final

import code_runner as cr

if TYPE_CHECKING:
    from collections.abc import Callable
    import random

type Json = Any
_LONG: Final = 400


def longest_substring(s: str) -> str:
    """Longest palindromic substring; the leftmost one on ties."""
    best = ""
    for centre in range(2 * len(s) - 1):
        lo, hi = centre // 2, centre // 2 + centre % 2
        while lo >= 0 and hi < len(s) and s[lo] == s[hi]:
            lo, hi = lo - 1, hi + 1
        if hi - lo - 1 > len(best):
            best = s[lo + 1 : hi]
    return best


def longest_substring_len(s: str) -> int:
    """Length of the longest palindromic substring."""
    return len(longest_substring(s))


def longest_subsequence_len(s: str) -> int:
    """Length of the longest palindromic subsequence."""
    n = len(s)
    dp = [[0] * n for _ in range(n)]
    for i in range(n - 1, -1, -1):
        dp[i][i] = 1
        for j in range(i + 1, n):
            if s[i] == s[j]:
                dp[i][j] = dp[i + 1][j - 1] + 2
            else:
                dp[i][j] = max(dp[i + 1][j], dp[i][j - 1])
    return dp[0][n - 1] if n else 0


@dataclass(frozen=True)
class PalinTask:
    """One variant: ``ref`` is the reference, inputs split visible / hidden."""

    key: str
    slug: str
    title: str
    statement: str
    starter: str
    ref: Callable[[str], Json]
    visible: tuple[str, ...]
    hidden: tuple[str, ...]


def _long(seed: int) -> str:
    stream = hashlib.shake_128(bytes([seed])).digest(_LONG)
    return "".join("abc"[b % 3] for b in stream)


_HIDDEN: Final = (
    "a",
    "ac",
    "aaaa",
    "abcd",
    "forgeeksskeegfor",
    "abacdfgdcaba",
    "racecarxyz",
    "xyzracecar",
    "bananas",
    "agbdba",
    "cbbdcbbdcbbd",
)
TASKS: Final = (
    PalinTask(
        "substr",
        "longest-palindromic-substring",
        "Longest palindromic substring",
        "Return the longest palindromic **substring** of `s` (contiguous). "
        "If several have the maximum length return the leftmost one. "
        "`1 <= len(s) <= 1000`.",
        "def longest_palindrome(s: str) -> str:\n    ",
        longest_substring,
        ("babad", "cbbd", "a"),
        (*_HIDDEN, _long(1)),
    ),
    PalinTask(
        "subseq",
        "longest-palindromic-subsequence",
        "Longest palindromic subsequence",
        "Return the **length** of the longest palindromic **subsequence** of "
        "`s` (characters in order, not necessarily contiguous). "
        "`1 <= len(s) <= 1000`.",
        "def longest_palindrome_subseq(s: str) -> int:\n    ",
        longest_subsequence_len,
        ("bbbab", "cbbd", "a"),
        (*_HIDDEN, _long(2)),
    ),
    PalinTask(
        "substr_len",
        "longest-palindromic-substring",
        "Longest palindromic substring: length",
        "Return the **length** of the longest palindromic **substring** of "
        "`s` (contiguous). `1 <= len(s) <= 1000`.",
        "def palindrome_length(s: str) -> int:\n    ",
        longest_substring_len,
        ("babad", "cbbd", "a"),
        (*_HIDDEN, _long(3)),
    ),
)


def pick(rnd: random.Random) -> PalinTask:
    """One variant at random."""
    return rnd.choice(TASKS)


def public(task: PalinTask) -> dict[str, Json]:
    """The task as the phone sees it (no hidden inputs, no answers)."""
    return {
        "id": "pc1",
        "section": "py_code",
        "title": task.title,
        "topic": "palindrome",
        "prompt_md": task.statement,
        "starter": task.starter,
    }


def _examples(task: PalinTask, inputs: tuple[str, ...], start: int) -> list[Any]:
    return [
        cr.Example(start + i, {"s": text}, task.ref(text))
        for i, text in enumerate(inputs)
    ]


def _short(value: object) -> object:
    return value if len(str(value)) < _LONG else "(long)"


def run(task: PalinTask, code: str, *, hidden: bool) -> list[Json]:
    """Run ``code``: the visible examples, or visible then hidden ones."""
    examples = _examples(task, task.visible, 1)
    if hidden:
        examples += _examples(task, task.hidden, len(task.visible) + 1)
    return [
        {
            "n": r.n,
            "ok": r.ok,
            "input": _short(r.input["s"]),
            "expected": _short(r.expected),
            "actual": _short(r.actual),
            "error": r.error,
        }
        for r in cr.run("python3", code, task.starter, examples)
    ]
