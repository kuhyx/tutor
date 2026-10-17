# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Markdown code in a model turn: the parts text repairs must not touch.

A question mark or an escape inside `inline code` or a ``` fenced block is code (a
ternary, a printf format), not prose. An unclosed fence runs to the end of
the text; a lone backtick is plain text.
"""

from __future__ import annotations

import re
from typing import Final

_CODE: Final = re.compile(r"```.*?(?:```|\Z)|`[^`]*`", re.DOTALL)


def pieces(text: str) -> list[tuple[str, bool]]:
    """``text`` cut into consecutive (chunk, is_code) pieces, none empty."""
    out: list[tuple[str, bool]] = []
    start = 0
    for found in _CODE.finditer(text):
        if found.start() > start:
            out.append((text[start : found.start()], False))
        out.append((found[0], True))
        start = found.end()
    if start < len(text):
        out.append((text[start:], False))
    return out
