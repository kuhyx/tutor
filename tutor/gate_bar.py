# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The quota bar: one segment per quota minute, the minutes done filled."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import tkinter as tk

    import gatelock

    from tutor.gate_state import Progress


def draw_bar(
    canvas: tk.Canvas, config: gatelock.LockConfig, progress: Progress | None
) -> None:
    """One segment per quota minute; the minutes done are filled."""
    canvas.delete("all")
    if progress is None:
        return
    width, height = int(canvas["width"]), int(canvas["height"])
    palette = config.palette
    gap = max(2, width // (progress.quota * 10))
    segment = (width - gap * (progress.quota - 1)) / progress.quota
    fill = palette.success if progress.paid else palette.accent
    # The unfilled track must differ from whatever the canvas sits on.
    track = palette.field_bg if str(canvas["bg"]) == palette.bg else palette.bg
    for minute in range(progress.quota):
        left = minute * (segment + gap)
        done = minute < progress.minutes
        canvas.create_rectangle(
            left,
            0,
            left + segment,
            height,
            width=0,
            fill=fill if done else track,
            tags=("done" if done else "todo",),
        )
