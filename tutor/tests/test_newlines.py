# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
r"""Literal ``\n`` from the model becomes a line break, except in code.

2026-10-17, live session 20261017-185723-ec8e: a turn read
"so here is the setup.\n\n"CI"" with the backslashes on the page.
"""

from __future__ import annotations

import pytest

from tutor import newlines

LIVE = 'so here is the setup.\\n\\n"CI"'


@pytest.mark.parametrize(
    ("said", "shown"),
    [
        (LIVE, 'so here is the setup.\n\n"CI"'),
        ('Run `printf("a\\n")` now.\\nOk?', 'Run `printf("a\\n")` now.\nOk?'),
        ("```\nputs 'a\\n'\n```\\nAfter", "```\nputs 'a\\n'\n```\nAfter"),
        ("a real\nbreak stays", "a real\nbreak stays"),
        ("one ` tick\\nthen", "one ` tick\nthen"),
        ("nothing to do", "nothing to do"),
    ],
    ids=["live", "inline-code", "fence", "real-newline", "lone-tick", "plain"],
)
def test_unescape_outside_code(said: str, shown: str) -> None:
    assert newlines.unescape(said) == shown
