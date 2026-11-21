# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""A published diagram must be drawable by the app (feedback 2026-10-15)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tutor.relay import media_out

if TYPE_CHECKING:
    from pathlib import Path

NAME = "6295ea4974bfa541-0.svg"
SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
    '<path d="M 0,0 L 5,5" style="stroke:black;fill:none;stroke-width:2.0;'
    'stroke-dasharray:-;stroke-linecap:round;"/></svg>'
)


def test_solid_line_dasharray_is_not_published(tmp_path: Path) -> None:
    (tmp_path / NAME).write_text(SVG, encoding="utf-8")
    node = media_out.diagram(NAME, "t", tmp_path)
    assert node is not None
    assert "dasharray" not in node["svg"]
    assert "stroke-width:2.0;stroke-linecap:round" in node["svg"]
