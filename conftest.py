# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Repo-wide: tests that count host processes run alone, even under pytest-xdist.

Every test holds a shared ``flock``; a test marked ``exclusive_host`` takes the
exclusive one, so it waits for the running tests to finish and blocks new ones
until it is done. That is what makes ``pgrep`` before/after counts and
fork-bomb tests exact while the rest of the suite runs in parallel workers.
The lock is machine-wide (``/tmp``): ``pgrep`` sees other sessions too.
"""

from __future__ import annotations

import fcntl
import getpass
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

_ROOT = Path(__file__).resolve().parent
_VENV_PYTHON = _ROOT / ".venv" / "bin" / "python"
_REEXEC = "TUTOR_PYTEST_REEXEC"
_GATE_SKIPPED = pytest.StashKey[bool]()


def _in_repo_venv() -> bool:
    """True when this interpreter is the repo's ``.venv`` (or there is none)."""
    if not _VENV_PYTHON.is_file() or os.environ.get(_REEXEC):
        return True
    return Path(sys.prefix).resolve() == (_ROOT / ".venv").resolve()


def _reexec_in_venv(config: pytest.Config) -> None:
    """Run again under the repo's venv when started from another interpreter.

    A board's done check calls the system ``python3``, which has none of
    tutor's dependencies; the suite only works in the venv. Global output
    capture is stopped first: it has the real stdout swapped for a temp file.
    The child's exit code is this process's; nothing else of this run is left
    (``os._exit``: no coverage report of a run that collected nothing).
    """
    if _in_repo_venv():
        return
    capture = config.pluginmanager.getplugin("capturemanager")
    if capture is not None:
        capture.stop_global_capturing()
    argv = [str(_VENV_PYTHON), "-m", "pytest", *sys.argv[1:]]
    run = subprocess.run(argv, env={**os.environ, _REEXEC: "1"}, check=False)
    sys.stdout.flush()
    os._exit(run.returncode)


# Before any ``tutor`` import: the tests pin card ids of a frozen deck, so a
# redraft of the real one (``redraft deck``) never breaks them.
os.environ["TUTOR_DECK_DIR"] = str(Path(__file__).parent / "tests/fixtures/deck")
_LOCK = Path(tempfile.gettempdir()) / f"tutor-tests-{getpass.getuser()}.lock"


def pytest_configure(config: pytest.Config) -> None:
    """Register the marker; a ``-k`` subset skips the whole-suite coverage gate.

    pyproject's ``--cov-fail-under=100`` measures the whole suite, so a
    keyword subset (a done check such as ``-k card_code_field``) always
    failed it. The full run (CI) and the commit stamp, which never pass
    ``-k``, still enforce 100 %.
    """
    _reexec_in_venv(config)
    config.addinivalue_line(
        "markers",
        "exclusive_host: counts host processes; runs with no other test running",
    )
    cov = config.pluginmanager.getplugin("_cov")
    if config.option.keyword and cov is not None and cov.options.cov_fail_under:
        cov.options.cov_fail_under = 0
        config.stash[_GATE_SKIPPED] = True


def pytest_terminal_summary(
    terminalreporter: pytest.TerminalReporter, config: pytest.Config
) -> None:
    """Say so when a ``-k`` run skipped the coverage gate."""
    if config.stash.get(_GATE_SKIPPED, False):
        terminalreporter.write_line("-k subset: whole-suite coverage gate skipped")


@pytest.fixture(autouse=True)
def _host_lock(request: pytest.FixtureRequest) -> Iterator[None]:
    exclusive = request.node.get_closest_marker("exclusive_host") is not None
    with _LOCK.open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        yield
