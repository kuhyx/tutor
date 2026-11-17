# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Open the tutor page in the user's real browser, detached.

``webbrowser`` is avoided: its ``BROWSER`` handling can run a terminal browser
in process, which under a Tk lock is a hang with the screen still grabbed. An
explicit ``Popen`` of a resolved path has no such mode. ``start_new_session``
keeps the browser alive when the gate (and its unit) stops.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import shutil
import subprocess
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

TUTOR_URL: Final = "http://127.0.0.1:8778/app/"
OPENERS: Final = ("xdg-open", "x-www-browser", "firefox")
_logger: Final = logging.getLogger(__name__)


@dataclass(frozen=True)
class LaunchResult:
    """What came of trying to open a URL."""

    ok: bool
    reason: str


def find_opener() -> str | None:
    """The first available opener's path, or ``None``.

    Asked *before* the lock is stood down: suspending the grab and only then
    finding nothing to launch would leave the machine open for no benefit.
    """
    for candidate in OPENERS:
        found = shutil.which(candidate)
        if found is not None:
            return found
    return None


def launch(url: str, *, spawn: Callable[..., Any] | None = None) -> LaunchResult:
    """Open ``url`` detached. Never raises: the grab is already down when it runs."""
    opener = find_opener()
    if opener is None:
        return LaunchResult(ok=False, reason="no browser launcher found")
    command: Sequence[str] = (opener, url)
    run = spawn if spawn is not None else subprocess.Popen
    try:
        run(command, start_new_session=True)
    except (OSError, ValueError) as exc:
        _logger.exception("could not open %s", url)
        return LaunchResult(ok=False, reason=f"{opener} failed: {exc}")
    _logger.info("opened %s with %s", url, opener)
    return LaunchResult(ok=True, reason=f"opened with {opener}")
