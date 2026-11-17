# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Study mode: stand the lock down so the browser gets keys, then put it back.

The HARD lock holds an X *global* grab, so no other client receives a key. An
"open tutor" button that only launched a browser would open one that swallows
every keystroke (leetcode-guard 2026-08-05). The grab has to come down.

Deliberate, like leetcode-guard's study mode: between ``suspend`` and
``resume`` the machine is NOT locked and there is no timeout; it ends when the
credit lands (the window closes), on "back to lock", or on "end evening".

Only gatelock's public API is used. Order matters: stop the recovery loop and
the output detector FIRST (left running they re-take the grab within a tick),
report the grab gone, release it, then hide. Resume strengthens before it
grabs (surfaces, VT) and restarts the loops unconditionally, even after a
failed re-grab: the loop is what heals a grab a browser still holds.
VT: ``LockWindow`` keeps its own "VT disabled" flag untouched, so its close
still restores VT exactly once more, which is harmless.
"""

from __future__ import annotations

import logging
import tkinter as tk
from typing import TYPE_CHECKING, Final

import gatelock

if TYPE_CHECKING:
    from collections.abc import Callable

REGRAB_ATTEMPTS: Final = 8
_logger: Final = logging.getLogger(__name__)


class StudySession:
    """Suspends and restores one ``gatelock.LockWindow``."""

    def __init__(
        self,
        lock: gatelock.LockWindow,
        config: gatelock.LockConfig,
        *,
        on_fail: Callable[[], None],
    ) -> None:
        """Wire to a live window; ``on_fail`` runs when the grab is not re-taken."""
        self._lock = lock
        self._config = config
        self._on_fail = on_fail
        self._active = False
        self._vt_restored = False
        self._regrabbed = False

    @property
    def active(self) -> bool:
        """Whether the lock is currently stood down."""
        return self._active

    def suspend(self) -> bool:
        """Release the grab and hide the surfaces. ``False`` = lock untouched/back."""
        if self._active:
            return True
        if not self._stop_loops():
            return False
        try:
            self._lock.report_grab_held(held=False)  # fail closed: say it first
            self._lock.root.grab_release()
        except tk.TclError:
            _logger.exception("could not release the grab; keeping the lock")
            self._lock.report_grab_held(held=True)
            self._start_loops()
            return False
        try:
            self._hide()
        except Exception:  # pylint: disable=broad-exception-caught
            # A wedged timer or a gatelock bug must not leave the grab released
            # with the state still saying locked.
            _logger.exception("study mode failed half-way; putting the lock back")
            self._restore()
            return False
        self._active = True
        _logger.warning("study mode ON: the grab is released, NOT locked")
        return True

    def resume(self) -> bool:
        """Put surfaces, VT and the grab back. ``False`` = grab not yet re-taken."""
        if not self._active:
            return True
        self._active = False
        regrabbed = self._restore()
        _logger.warning("study mode OFF; the lock is back (grab=%s)", regrabbed)
        return regrabbed

    def _stop_loops(self) -> bool:
        try:
            self._lock.recovery.stop()
            self._lock.detector.stop()
        except tk.TclError:
            _logger.exception("could not stop the loops; refusing study mode")
            self._start_loops()
            return False
        return True

    def _hide(self) -> None:
        if self._config.resolved_disable_vt():
            self._vt_restored = True  # before the call: if it raises we don't know
            gatelock.restore_vt_switching()
        self._lock.surfaces.set_visible(visible=False)
        self._lock.root.withdraw()

    def _restore(self) -> bool:
        """Everything back, strongest first; the loops restart whatever happens."""
        for step in (self._map_root, self._vt_back, self._show):
            self._guarded(step)
        self._guarded(self._regrab)
        regrabbed = self._regrabbed
        self._start_loops()
        if not regrabbed:
            self._on_fail()
        return regrabbed

    @staticmethod
    def _guarded(step: Callable[[], None]) -> None:
        """Run one restore step; one failing must not skip the ones after it."""
        try:
            step()
        except Exception:  # pylint: disable=broad-exception-caught
            _logger.exception("a restore step failed; continuing")

    def _map_root(self) -> None:
        self._lock.root.deiconify()
        self._lock.root.update_idletasks()

    def _vt_back(self) -> None:
        if self._vt_restored:
            self._vt_restored = False
            gatelock.disable_vt_switching()

    def _show(self) -> None:
        self._lock.surfaces.set_visible(visible=True)

    def _regrab(self) -> None:
        self._regrabbed = False
        for _ in range(REGRAB_ATTEMPTS):
            try:
                self._lock.root.focus_force()
                if self._config.resolved_grab() == "global":
                    self._lock.root.grab_set_global()
                else:
                    self._lock.root.grab_set()
            except tk.TclError:
                _logger.warning("the grab is not available yet", exc_info=True)
                continue
            self._lock.report_grab_held(held=True)
            self._regrabbed = True
            return

    def _start_loops(self) -> None:
        for name in ("detector", "recovery"):
            try:
                getattr(self._lock, name).start()
            except tk.TclError:
                _logger.exception("could not restart the %s loop", name)
