# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The evening gate's widgets: a quota bar and two controls, no words (textgate).

Numerals and BMP pictograms only (Tk 8.6 can crash on colour emoji). Tokens come
from ``gatelock.LockConfig``; sizes scale with output height (4K is not phone-sized).
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import tkinter as tk
from typing import TYPE_CHECKING, Final

import gatelock

from tutor import gate_bar

if TYPE_CHECKING:
    from collections.abc import Callable

    from tutor.gate_state import Progress

OPEN: Final = "↗"
END: Final = "✕"
BACK: Final = "↩"
WARN: Final = "⚠"
_BASE_HEIGHT: Final = 1080  # the height the token scale is authored for
_STRIP_TICK_MS: Final = 1000
_logger: Final = logging.getLogger(__name__)


@dataclass(frozen=True)
class Controls:
    """What the two controls do."""

    primary: Callable[[], None]
    end: Callable[[], None]


@dataclass(frozen=True)
class Size:
    """A surface's pixel size."""

    width: int
    height: int

    @property
    def scale(self) -> float:
        """1.0 up to 1080p, larger above it (2.0 on 4K)."""
        return max(1.0, self.height / _BASE_HEIGHT)


def _control(
    parent: tk.Misc,
    config: gatelock.LockConfig,
    mark: str,
    command: Callable[[], None],
    look: tuple[gatelock.ButtonVariant, float],
) -> tk.Button:
    """A glyph button from the shared palette, enlarged for the output."""
    button: tk.Button = gatelock.make_button(
        parent, config, mark, command, gatelock.ButtonStyle(variant=look[0])
    )
    button.configure(
        font=config.font("display", bold=True, scale=look[1]),
        padx=int(36 * look[1]),
        pady=int(18 * look[1]),
    )
    return button


class Panel:
    """The lock surface's content: minutes/quota, the bar, open and end."""

    def __init__(
        self,
        parent: tk.Misc,
        config: gatelock.LockConfig,
        size: Size,
        *,
        on_open: Callable[[], None],
        on_end: Callable[[], None],
    ) -> None:
        """Build the panel centred in ``parent``."""
        self._config = config
        palette, scale = config.palette, size.scale
        self.frame = tk.Frame(parent, bg=palette.bg)
        self.frame.pack(fill="both", expand=True)
        inner = tk.Frame(self.frame, bg=palette.bg)
        inner.place(relx=0.5, rely=0.5, anchor="center")
        self.count = tk.Label(
            inner,
            bg=palette.bg,
            fg=palette.fg,
            font=config.font("display", bold=True, scale=scale * 1.5),
        )
        self.count.pack(pady=config.space("lg"))
        self.quota_bar = tk.Canvas(
            inner,
            width=int(size.width * 0.5),
            height=int(36 * scale),
            bg=palette.bg,
            highlightthickness=0,
        )
        self.quota_bar.pack(pady=config.space("lg"))
        row = tk.Frame(inner, bg=palette.bg)
        row.pack(pady=config.space("xl"))
        pad = config.space("lg")
        self.open_button = _control(row, config, OPEN, on_open, look=("primary", scale))
        self.open_button.pack(side="left", padx=pad)
        self.end_button = _control(row, config, END, on_end, look=("danger", scale))
        self.end_button.pack(side="left", padx=pad)
        self.warn = tk.Label(
            inner,
            bg=palette.bg,
            fg=palette.warning,
            font=config.font("title", scale=scale),
        )
        self.warn.pack()

    def update(self, progress: Progress | None) -> None:
        """Repaint from ``progress``; ``None`` = could not check (warning mark)."""
        gate_bar.draw_bar(self.quota_bar, self._config, progress)
        if progress is None:
            self.count.configure(text="")
            self.set_warning(show=True)
            return
        self.count.configure(text=f"{progress.minutes}/{progress.quota}")
        self.set_warning(show=False)

    def set_warning(self, *, show: bool) -> None:
        """Show or clear the warning mark."""
        self.warn.configure(text=WARN if show else "")


class Strip:
    """The small always-on-top window that stays while the lock is stood down."""

    def __init__(
        self,
        window: tk.Toplevel,
        quota_bar: tk.Canvas,
        config: gatelock.LockConfig,
        buttons: tuple[tk.Button, tk.Button],
    ) -> None:
        """Wrap an already-built strip window; ``buttons`` = (back, end)."""
        self.window = window
        self.back_button, self.end_button = buttons
        self.quota_bar = quota_bar
        self._config = config
        self._job: str | None = None
        self._destroyed = False

    def update(self, progress: Progress | None) -> None:
        """Repaint the bar."""
        if not self._destroyed:
            gate_bar.draw_bar(self.quota_bar, self._config, progress)

    def lift_tick(self) -> None:
        """Stay on top: nothing else re-lifts while the recovery loop is stopped."""
        if self._destroyed:
            return
        try:
            self.window.lift()
        except tk.TclError:
            _logger.warning("the strip could not be lifted", exc_info=True)

    def schedule(self) -> None:
        """Re-lift every second until destroyed."""

        def run() -> None:
            self.lift_tick()
            if not self._destroyed:
                self._job = self.window.after(_STRIP_TICK_MS, run)

        self._job = self.window.after(_STRIP_TICK_MS, run)

    def destroy(self) -> None:
        """Cancel the tick and tear the window down. Idempotent."""
        if self._destroyed:
            return
        self._destroyed = True
        try:
            if self._job is not None:
                self.window.after_cancel(self._job)
            self.window.destroy()
        except tk.TclError:
            _logger.warning("the strip could not be destroyed", exc_info=True)


def _strip_window(
    root: tk.Misc,
    config: gatelock.LockConfig,
    rect: gatelock.OutputRect,
    size: tuple[int, int],
) -> tk.Toplevel:
    """An override-redirect, topmost window at the top-right of ``rect``."""
    window = tk.Toplevel(root)
    window.withdraw()  # override-redirect only takes effect while unmapped
    window.overrideredirect(boolean=True)
    window.configure(bg=config.palette.field_bg)
    inset = config.space("md")
    window.geometry(
        f"{size[0]}x{size[1]}+{rect.x + rect.width - size[0] - inset}+{rect.y + inset}"
    )
    window.deiconify()
    window.lift()
    window.attributes("-topmost", 1)
    return window


def build_strip(
    root: tk.Misc,
    config: gatelock.LockConfig,
    rect: gatelock.OutputRect,
    progress: Progress | None,
    controls: Controls,
) -> Strip:
    """Create the strip at the top-right of ``rect`` (the primary output)."""
    scale = Size(rect.width, rect.height).scale
    palette = config.palette
    width = int(560 * scale)
    window = _strip_window(root, config, rect, (width, int(180 * scale)))
    pad = config.space("md")
    quota_bar = tk.Canvas(
        window,
        width=width - 2 * pad,
        height=int(24 * scale),
        bg=palette.field_bg,
        highlightthickness=0,
    )
    quota_bar.pack(pady=pad)
    row = tk.Frame(window, bg=palette.field_bg)
    row.pack()
    back = _control(row, config, BACK, controls.primary, look=("primary", scale))
    back.pack(side="left", padx=pad)
    end = _control(row, config, END, controls.end, look=("danger", scale))
    end.pack(side="left", padx=pad)
    strip = Strip(window, quota_bar, config, (back, end))
    strip.update(progress)
    strip.schedule()
    return strip
