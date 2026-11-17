# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The gate's widgets: a quota bar, two controls, and no words (textgate)."""

from __future__ import annotations

import os
import re
import time
import tkinter as tk
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import gatelock
import pytest

from tutor import gate_view
from tutor.gate_state import Progress

if TYPE_CHECKING:
    from collections.abc import Iterator

CONFIG = gatelock.LockConfig()
RECT: gatelock.OutputRect = gatelock.OutputRect(x=0, y=0, width=3840, height=2160)
# Numerals, a slash, whitespace and the four pictograms: nothing else is allowed.
ONLY_MARKS = re.compile(r"[\d\s/↗✕↩⚠]*")


@pytest.fixture
def root() -> Iterator[tk.Tk]:
    if not os.environ.get("DISPLAY"):
        pytest.skip("no X display (run under xvfb-run)")
    window = tk.Tk()
    window.geometry("1000x700")
    yield window
    window.destroy()


def _texts(widget: tk.Misc) -> list[str]:
    found: list[str] = []
    for child in [widget, *widget.winfo_children()]:
        if isinstance(child, tk.Label | tk.Button):
            found.append(str(child.cget("text")))
        if child is not widget:
            found.extend(_texts(child))
    return found


def _panel(root: tk.Tk, calls: list[str]) -> gate_view.Panel:
    return gate_view.Panel(
        root,
        CONFIG,
        gate_view.Size(width=1920, height=1080),
        on_open=lambda: calls.append("open"),
        on_end=lambda: calls.append("end"),
    )


def test_the_bar_has_one_segment_per_quota_minute(root: tk.Tk) -> None:
    panel = _panel(root, [])
    panel.update(Progress(minutes=7, quota=15, paid=False))
    assert len(panel.quota_bar.find_withtag("done")) == 7
    assert len(panel.quota_bar.find_withtag("todo")) == 8
    panel.update(Progress(minutes=15, quota=15, paid=True))
    assert len(panel.quota_bar.find_withtag("done")) == 15
    assert not panel.quota_bar.find_withtag("todo")


def test_both_controls_are_there_at_zero_minutes_and_call_back(root: tk.Tk) -> None:
    calls: list[str] = []
    panel = _panel(root, calls)
    panel.update(Progress(minutes=0, quota=50, paid=False))
    panel.open_button.invoke()
    panel.end_button.invoke()
    assert calls == ["open", "end"]


def test_the_panel_says_nothing_but_marks(root: tk.Tk) -> None:
    panel = _panel(root, [])
    panel.update(Progress(minutes=7, quota=15, paid=False))
    panel.set_warning(show=True)
    texts = _texts(panel.frame)
    assert "7/15" in texts
    assert all(ONLY_MARKS.fullmatch(t) for t in texts), texts


def test_could_not_check_shows_the_warning_mark_and_no_bar_fill(root: tk.Tk) -> None:
    panel = _panel(root, [])
    panel.update(None)
    assert not panel.quota_bar.find_withtag("done")
    assert gate_view.WARN in _texts(panel.frame)
    panel.update(Progress(minutes=1, quota=15, paid=False))
    assert gate_view.WARN not in _texts(panel.frame)


def test_a_spawn_failure_can_be_flagged_and_cleared(root: tk.Tk) -> None:
    panel = _panel(root, [])
    panel.update(Progress(minutes=1, quota=15, paid=False))
    panel.set_warning(show=True)
    assert gate_view.WARN in _texts(panel.frame)
    panel.set_warning(show=False)
    assert gate_view.WARN not in _texts(panel.frame)


def test_the_strip_has_back_and_end_and_follows_progress(root: tk.Tk) -> None:
    calls: list[str] = []
    strip = gate_view.build_strip(
        root,
        CONFIG,
        RECT,
        Progress(minutes=3, quota=15, paid=False),
        gate_view.Controls(
            primary=lambda: calls.append("back"), end=lambda: calls.append("end")
        ),
    )
    strip.back_button.invoke()
    strip.end_button.invoke()
    assert calls == ["back", "end"]
    assert len(strip.quota_bar.find_withtag("done")) == 3
    strip.update(Progress(minutes=9, quota=15, paid=False))
    assert len(strip.quota_bar.find_withtag("done")) == 9
    assert all(ONLY_MARKS.fullmatch(t) for t in _texts(strip.window))
    strip.destroy()
    strip.destroy()  # idempotent
    strip.update(None)  # a dead strip ignores updates


def test_the_strip_sits_top_right_of_its_output_and_stays_on_top(root: tk.Tk) -> None:
    strip = gate_view.build_strip(
        root,
        CONFIG,
        RECT,
        None,
        gate_view.Controls(primary=lambda: None, end=lambda: None),
    )
    strip.window.update()
    assert strip.window.winfo_x() > RECT.width // 2
    assert strip.window.winfo_y() < 200
    strip.lift_tick()
    strip.destroy()
    strip.lift_tick()  # after destroy: no TclError escapes


def test_the_strip_relifts_itself_every_tick(
    root: tk.Tk, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gate_view, "_STRIP_TICK_MS", 5)
    strip = gate_view.build_strip(
        root, CONFIG, RECT, None, gate_view.Controls(lambda: None, lambda: None)
    )
    lifts: list[int] = []
    monkeypatch.setattr(strip, "lift_tick", lambda: lifts.append(1))
    for _ in range(40):
        root.update()
        time.sleep(0.005)
    assert len(lifts) >= 1
    strip.destroy()


def test_a_strip_whose_window_died_is_survived(root: tk.Tk) -> None:
    strip = gate_view.build_strip(
        root, CONFIG, RECT, None, gate_view.Controls(lambda: None, lambda: None)
    )
    strip.window.destroy()
    strip.lift_tick()
    strip.destroy()


def test_a_strip_that_never_ticked_destroys_cleanly(root: tk.Tk) -> None:
    window = tk.Toplevel(root)
    gate_view.Strip(
        window, tk.Canvas(window), CONFIG, (tk.Button(window), tk.Button(window))
    ).destroy()


def test_a_window_that_cannot_be_destroyed_is_logged_not_raised(
    root: tk.Tk, caplog: pytest.LogCaptureFixture
) -> None:
    strip = gate_view.build_strip(
        root, CONFIG, RECT, None, gate_view.Controls(lambda: None, lambda: None)
    )
    real = strip.window
    broken = MagicMock()
    broken.destroy.side_effect = tk.TclError("gone")
    strip.window = broken
    strip.destroy()
    assert "could not be destroyed" in caplog.text
    real.destroy()


def test_a_tick_that_ends_the_strip_does_not_reschedule(
    root: tk.Tk, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gate_view, "_STRIP_TICK_MS", 5)
    strip = gate_view.build_strip(
        root, CONFIG, RECT, None, gate_view.Controls(lambda: None, lambda: None)
    )
    monkeypatch.setattr(strip, "lift_tick", strip.destroy)
    for _ in range(40):
        root.update()
        time.sleep(0.005)
    assert strip.window.winfo_exists() == 0
