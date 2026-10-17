# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
r"""Line breaks the model wrote as the two characters ``\n``.

The model sometimes escapes a newline twice, so the page showed a backslash
and an "n" where a paragraph break belonged (live session
20261017-185723-ec8e). :func:`unescape` turns them into real newlines in the
message, the questions and the check, but never inside code, where ``\n``
is meant literally (a printf format).
"""

from __future__ import annotations

from tutor import codespans


def unescape(text: str) -> str:
    r"""``text`` with every literal ``\n`` outside code made a real newline."""
    return "".join(
        chunk if code else chunk.replace("\\n", "\n")
        for chunk, code in codespans.pieces(text)
    )
