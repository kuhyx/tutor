# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""A model call that fails is filed on the shared app-errors board, once.

Two faults, both reported to the spool of kuhy's app-errors pipeline (utils
``DOCS-app-errors.md``; the PC ingest turns an entry into a todoImplementer
fix task) as app ``tutor``, repo ``kuhyx/tutor``:

* **The model sandbox will not start.** ``scripts/tutor_model_sandbox.sh`` and
  ``tutor_model_netfence.sh`` name themselves on stderr (``tutor_model_netfence:
  the egress filter did not load; not starting``). :meth:`Monitor.stderr_line`
  sees that line through the SDK's ``stderr`` callback (installed by
  ``TutorSession``) and files :data:`SANDBOX_KIND`, plus one desktop toast that
  is an icon only (textgate: no words). Every call fails until the PC is fixed
  or restarted, so the toast and the entry come once per *streak*: until the
  next model call succeeds (:meth:`Monitor.succeeded`).
* **Any other model failure** (CLI died, error result, timeout, no start) is
  filed as :data:`ERROR_KIND`, with no toast. An API outage is not a fault
  (``ClaudeUnavailableError``: the app already shows it) and is never filed.

Reporting never raises into the model path. The reporter is gatelock's
(``gatelock.error_report.Reporter``): it dedupes, caps per minute and writes
``$XDG_STATE_HOME/app-errors-spool/tutor.jsonl``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import shutil
import subprocess
from typing import TYPE_CHECKING, Any, Final

from gatelock.error_report import Reporter

from tutor.outage import ClaudeUnavailableError

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

APP: Final = "tutor"
REPO: Final = "kuhyx/tutor"
SANDBOX_KIND: Final = "model.sandbox"
ERROR_KIND: Final = "model.error"
# The scripts' own stderr prefixes: the sandbox wrapper and the egress fence.
_SANDBOX_MARKS: Final = ("tutor_model_netfence", "tutor_model_sandbox")
_TOAST_ICON: Final = "system-reboot"
_TOAST_GLYPH: Final = "⟳"  # a pictogram summary: notify-send needs one
_TOAST_TIMEOUT: Final = 10
_DETAIL: Final = 120
_logger = logging.getLogger(__name__)


class SandboxStartError(RuntimeError):
    """The model sandbox (bubblewrap wrapper or network fence) did not start."""


def notify_argv(binary: str) -> list[str]:
    """``notify-send`` with a restart icon, critical urgency and no words."""
    return [binary, "-a", APP, "-u", "critical", "-i", _TOAST_ICON, _TOAST_GLYPH]


def send_toast(
    run: Callable[..., Any] = subprocess.run,
    which: Callable[[str], str | None] = shutil.which,
) -> None:
    """Show the restart-icon toast; skipped without ``notify-send``, never raises."""
    binary = which("notify-send")
    if binary is None:
        return
    try:
        run(notify_argv(binary), check=False, timeout=_TOAST_TIMEOUT)
    except OSError, subprocess.SubprocessError:
        _logger.warning("the sandbox-fault toast was not shown", exc_info=True)


def _line(err: BaseException) -> str:
    """``Type: first line of the message``, short (the board groups on it)."""
    first = (str(err).strip().splitlines() or [""])[0][:_DETAIL]
    return f"{type(err).__name__}: {first}".rstrip(": ")


@dataclass
class Monitor:
    """Files model faults; one toast and one sandbox entry per failure streak.

    ``spool`` (None: the user's ``app-errors-spool``) and ``notify`` are test
    seams: tests point both at a temp dir and a recorder.
    """

    spool: Path | None = None
    notify: Callable[[], None] = send_toast
    _sandbox_down: bool = field(default=False, init=False)
    _reporter: Any = field(default=None, init=False, repr=False)

    def _report(self, kind: str, error: object) -> None:
        """Hand ``error`` to the spool reporter; its failures stay in the log."""
        try:
            if self._reporter is None:
                args: dict[str, Any] = {"mark": "tutor/"}
                if self.spool is not None:
                    args["spool"] = self.spool
                self._reporter = Reporter(APP, REPO, **args)
            self._reporter.report(kind, error)
        except Exception:  # pylint: disable=broad-exception-caught
            _logger.exception("model fault not reported")

    def stderr_line(self, line: str) -> None:
        """One line of the model CLI's stderr (the SDK's ``stderr`` callback)."""
        if self._sandbox_down or not any(mark in line for mark in _SANDBOX_MARKS):
            return
        self._sandbox_down = True
        _logger.error("model sandbox did not start: %s", line.strip())
        self._report(SANDBOX_KIND, SandboxStartError(line.strip()))
        try:
            self.notify()
        except Exception:  # pylint: disable=broad-exception-caught
            _logger.exception("the sandbox-fault toast failed")

    def failed(self, err: BaseException) -> None:
        """A model call failed with ``err``: file it, unless it is already filed."""
        if self._sandbox_down or isinstance(err, ClaudeUnavailableError):
            return  # the sandbox entry covers it / an outage is not a fault
        self._report(ERROR_KIND, _line(err))

    def succeeded(self) -> None:
        """A model call answered: the next sandbox failure is a new streak."""
        self._sandbox_down = False


#: The process's monitor; tests replace it (``conftest.fault``).
MONITOR: Monitor = Monitor()


def watch(chained: Callable[[str], None] | None = None) -> Callable[[str], None]:
    """SDK ``stderr`` callback: the monitor sees each line, then ``chained``."""

    def on_line(line: str) -> None:
        MONITOR.stderr_line(line)
        if chained is not None:
            chained(line)

    return on_line
