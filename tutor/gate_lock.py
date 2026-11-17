# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The tutor evening lock window (HARD gatelock, arbiter rank 150).

Shows today's minutes against the quota as a bar, plus two controls that work
from t=0 under the grab: open the tutor (study mode: the grab comes down so the
browser gets keys) and end the evening (exit 10; the chain stops and night
lockdown follows at the next root tick). A credit landing closes the window
(exit 0) within ~3 s through ``gatelock.watch_credit``.

No words on screen (textgate): numerals and pictograms only.
"""

from __future__ import annotations

import importlib
import logging
from traceback import format_exc
from typing import TYPE_CHECKING, Final

import gatelock

from tutor import gate_open, gate_view
from tutor.gate_state import Progress, local_today, read_progress
from tutor.gate_study import StudySession

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import date
    import tkinter as tk

    from tutor.ledger_io import Paths

RANK_TUTOR_EVENING: Final = 150
_END_EVENING_FALLBACK: Final = 10
_logger: Final = logging.getLogger(__name__)


def end_evening_code() -> int:
    """The chain's "end evening" exit code, 10 when its module is not there yet."""
    try:
        chain = importlib.import_module("gatelock.evening_chain")
    except ImportError:
        _logger.warning("gatelock.evening_chain missing; end-evening exit is 10")
        return _END_EVENING_FALLBACK
    return int(getattr(chain, "EXIT_END_EVENING", _END_EVENING_FALLBACK))


class EveningLock:
    """A gatelock consumer that releases once today's tutor quota is paid."""

    def __init__(
        self,
        paths: Paths,
        progress: Progress | None,
        *,
        today: Callable[[], date] = local_today,
        production: bool,
        opener: Callable[[str], gate_open.LaunchResult] = gate_open.launch,
    ) -> None:
        """Arm the lock. Demo mode (``production=False``) takes a local grab."""
        gatelock.assert_not_under_pytest("the tutor evening gate")
        self.exit_code = 0
        self.panels: dict[str, gate_view.Panel] = {}
        self.strip: gate_view.Strip | None = None
        self._paths = paths
        self._today = today
        self._progress = progress
        self._opener = opener
        self._closed = False
        config = gatelock.LockConfig(
            mode="hard",
            overrideredirect=True,
            grab=gatelock.GrabPolicy(
                kind="global" if production else "local", disable_vt=production
            ),
            app_name="tutor_gate",
            rank=RANK_TUTOR_EVENING,
        )
        self._config = config
        self.root: tk.Tk = gatelock.GateRoot()
        self.root.title("tutor_gate")
        arbiter = gatelock.Arbiter(
            "tutor_gate",
            RANK_TUTOR_EVENING,
            grab=config.resolved_grab(),
            disable_vt=config.resolved_disable_vt(),
        )
        arbiter.publish()
        if production:
            gatelock.wait_for_turn(arbiter)
        arbiter.acquire_holder()
        self._lock = gatelock.LockWindow(self.root, config, hooks=self, arbiter=arbiter)
        self.study = StudySession(self._lock, config, on_fail=self._flag_failure)
        self._lock.setup()
        self._lock.grab_input()
        gatelock.watch_credit(
            self.root,
            [paths.ledger],
            self._check,
            self.close_paid,
            poll_ms=gatelock.CREDIT_POLL_MS,
        )

    # -- gatelock hooks -------------------------------------------------------

    def build_surface(self, parent: tk.Misc, surface: gatelock.SurfaceInfo) -> None:
        """Paint one output. Every output gets the controls: none is a dead end."""
        size = gate_view.Size(surface.rect.width, surface.rect.height)
        panel = gate_view.Panel(
            parent, self._config, size, on_open=self.open_tutor, on_end=self.end_evening
        )
        panel.update(self._progress)
        self.panels[surface.output_name] = panel

    def teardown_surface(self, surface: gatelock.SurfaceInfo) -> None:
        """Forget a panel whose output went away."""
        self.panels.pop(surface.output_name, None)

    def on_focus_ready(self, surface: gatelock.SurfaceInfo | None) -> None:
        """Nothing takes keyboard input here."""

    def on_callback_error(self) -> None:
        """A Tk callback raised: log it, mark the surfaces, keep the lock up."""
        _logger.error("a Tk callback raised inside the lock:\n%s", format_exc())
        self._flag_failure()

    def on_close(self) -> None:
        """Every exit path: drop the strip."""
        self._drop_strip()

    # -- behaviour --------------------------------------------------------------

    def _check(self) -> bool:
        """The credit watch's verdict; repaints the bar from the same read."""
        progress = read_progress(self._paths, self._today())
        self._progress = progress
        for panel in self.panels.values():
            panel.update(progress)
        if self.strip is not None:
            self.strip.update(progress)
        return progress is not None and progress.paid

    def close_paid(self) -> None:
        """The credit landed: close with exit 0."""
        self.exit_code = 0
        self.close()

    def end_evening(self) -> None:
        """The way out from t=0: close with the chain's end-evening code."""
        self.exit_code = end_evening_code()
        self.close()

    def open_tutor(self) -> None:
        """Stand the lock down, then open the tutor page, in that order.

        No browser means no suspend (the machine would be open for nothing); a
        launch that fails puts the lock straight back.
        """
        if self.study.active:
            self._spawn()
            return
        if gate_open.find_opener() is None:
            _logger.warning("no browser launcher; the lock is unchanged")
            self._flag_failure()
            return
        if not self.study.suspend():
            self._flag_failure()
            return
        if not self._spawn():
            self.study.resume()
            return
        self._show_strip()

    def _spawn(self) -> bool:
        try:
            result = self._opener(gate_open.TUTOR_URL)
        except Exception:  # pylint: disable=broad-exception-caught
            _logger.exception("the opener raised; treating it as a failure")
            self._flag_failure()
            return False
        if not result.ok:
            self._flag_failure()
        return result.ok

    def _show_strip(self) -> None:
        infos = self._lock.surfaces.infos()
        if not infos:
            _logger.warning("no output to place the study strip on")
            return
        primary = next((i for i in infos if i.is_primary), infos[0])
        self.strip = gate_view.build_strip(
            self.root,
            self._config,
            primary.rect,
            self._progress,
            gate_view.Controls(primary=self.back_to_lock, end=self.end_evening),
        )

    def back_to_lock(self) -> None:
        """Re-lock by request (the strip is destroyed before the grab returns)."""
        self._drop_strip()
        self.study.resume()

    def _drop_strip(self) -> None:
        if self.strip is not None:
            self.strip.destroy()
            self.strip = None

    def _flag_failure(self) -> None:
        for panel in self.panels.values():
            panel.set_warning(show=True)

    def close(self) -> None:
        """Release the lock. Idempotent."""
        if not self._closed:
            self._closed = True
            self._lock.close()

    def run(self) -> None:
        """Hand control to Tk until the lock releases."""
        self._lock.run()
