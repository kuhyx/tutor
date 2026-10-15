# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The Claude-unavailable window log (``unavailable``)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tutor import unavailable

if TYPE_CHECKING:
    from pathlib import Path


def test_record_uses_reset_time_else_default_span(tmp_path: Path) -> None:
    limited = unavailable.record("rate_limit", 1000, resets_at=5000, root=tmp_path)
    assert limited == unavailable.Window(1000, 5000, "rate_limit")
    stale = unavailable.record("network", 6000, resets_at=10, root=tmp_path)
    assert stale.end == 6000 + unavailable.DEFAULT_SPAN
    assert unavailable.windows(tmp_path) == [limited, stale]


def test_unknown_reason_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown"):
        unavailable.record("bored", 1, root=tmp_path)


def test_windows_skip_bad_lines_and_sort(tmp_path: Path) -> None:
    assert unavailable.windows(tmp_path) == []
    unavailable.path(tmp_path).write_text(
        '{"start": 50, "end": 60, "reason": "overloaded"}\nnot json\n'
        '{"start": 10}\n{"start": 1, "end": 9, "reason": "network"}\n',
        encoding="utf-8",
    )
    found = unavailable.windows(tmp_path)
    assert [w.start for w in found] == [1, 50]
    assert unavailable.unavailable_at(55, found)
    assert not unavailable.unavailable_at(9, found)


def test_current_picks_latest_ending_cover(tmp_path: Path) -> None:
    unavailable.record("network", 100, resets_at=200, root=tmp_path)
    unavailable.record("rate_limit", 150, resets_at=900, root=tmp_path)
    assert unavailable.current(160, tmp_path) == unavailable.Window(
        150, 900, "rate_limit"
    )
    assert unavailable.current(950, tmp_path) is None
