# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Shared rig for the evening-lock tests: fake gatelock window, real Tk widgets.

The gatelock window, arbiter and credit watch are replaced by recorders (a real
one would take the grab); the widgets are real Tk on the test display. Test
modules load the ``rig`` fixture with ``pytest_plugins``.
"""

from __future__ import annotations

import os
import tkinter as tk
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, ClassVar, cast
from unittest.mock import MagicMock

import gatelock
import pytest

from tutor import gate_lock, gate_open, gate_view
from tutor.gate_state import Progress
from tutor.tests import _gate_support as sup

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

PART = Progress(minutes=3, quota=15, paid=False)
FULL = Progress(minutes=15, quota=15, paid=True)


class Window:
    """A ``LockWindow`` that builds one surface into a real frame, grabs nothing."""

    instances: ClassVar[list[Window]] = []

    def __init__(self, root: tk.Tk, config: Any, hooks: Any, *, arbiter: Any) -> None:
        self.root, self.config, self.hooks, self.arbiter = root, config, hooks, arbiter
        self.closed = 0
        self.grabbed = False
        self.outputs: tuple[Any, ...] = ()
        type(self).instances.append(self)

    def setup(self) -> None:
        self.frame = tk.Frame(self.root, width=1000, height=700)
        self.frame.pack()
        self.surface = SimpleNamespace(
            output_name="DP-0",
            index=0,
            is_primary=True,
            rect=gatelock.OutputRect(x=0, y=0, width=1920, height=1080),
        )
        self.hooks.build_surface(self.frame, self.surface)
        self.outputs = (self.surface,)

    def grab_input(self) -> None:
        self.grabbed = True

    def close(self) -> None:
        self.closed += 1
        self.hooks.on_close()

    def run(self) -> None:
        self.ran = True

    @property
    def surfaces(self) -> SimpleNamespace:
        return SimpleNamespace(infos=lambda: self.outputs)


class FakeSession:
    def __init__(self, lock: Any, config: Any, *, on_fail: Callable[[], None]) -> None:
        self.on_fail = on_fail
        self.active = False
        self.suspend_ok = True
        self.log: list[str] = []

    def suspend(self) -> bool:
        self.log.append("suspend")
        self.active = self.suspend_ok
        return self.suspend_ok

    def resume(self) -> bool:
        self.log.append("resume")
        self.active = False
        return True


@pytest.fixture
def rig(monkeypatch: pytest.MonkeyPatch) -> Iterator[SimpleNamespace]:
    if not os.environ.get("DISPLAY"):
        pytest.skip("no X display (run under xvfb-run)")
    root = tk.Tk()
    arbiter = MagicMock()
    watch: dict[str, Any] = {}
    waited: list[Any] = []
    arbiters: list[dict[str, Any]] = []
    Window.instances = []

    def make_arbiter(*args: Any, **kwargs: Any) -> Any:
        arbiters.append({"args": args, **kwargs})
        return arbiter

    def watching(
        _root: Any, paths: Any, is_done: Any, on_credit: Any, poll_ms: int = 0
    ) -> None:
        watch.update(paths=paths, is_done=is_done, on_credit=on_credit, poll=poll_ms)

    monkeypatch.setattr(gatelock, "assert_not_under_pytest", lambda _w: None)
    monkeypatch.setattr(gatelock, "GateRoot", lambda: root)
    monkeypatch.setattr(gatelock, "LockWindow", Window)
    monkeypatch.setattr(gatelock, "Arbiter", make_arbiter)
    monkeypatch.setattr(gatelock, "wait_for_turn", waited.append)
    monkeypatch.setattr(gatelock, "watch_credit", watching)
    monkeypatch.setattr(gate_lock, "StudySession", FakeSession)
    monkeypatch.setattr(gate_lock, "end_evening_code", lambda: 10)
    monkeypatch.setattr(gate_open, "find_opener", lambda: "/bin/xdg-open")
    yield SimpleNamespace(
        root=root, arbiter=arbiter, watch=watch, waited=waited, arbiters=arbiters
    )
    root.destroy()


def recorder(opened: list[str]) -> Callable[[str], gate_open.LaunchResult]:
    def opener(url: str) -> gate_open.LaunchResult:
        opened.append(url)
        return gate_open.LaunchResult(ok=True, reason="")

    return opener


def make_lock(
    *,
    production: bool = True,
    progress: Progress | None = PART,
    opener: Callable[[str], gate_open.LaunchResult] | None = None,
) -> gate_lock.EveningLock:
    return gate_lock.EveningLock(
        sup.paths(),
        progress,
        today=lambda: sup.TUESDAY,
        production=production,
        opener=opener or (lambda _u: gate_open.LaunchResult(ok=True, reason="")),
    )


def session(lock: gate_lock.EveningLock) -> FakeSession:
    return cast("FakeSession", lock.study)


def buttons(lock: gate_lock.EveningLock) -> gate_view.Panel:
    return next(iter(lock.panels.values()))
