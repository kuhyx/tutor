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
from pathlib import Path
import tempfile
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

_LOCK = Path(tempfile.gettempdir()) / f"tutor-tests-{getpass.getuser()}.lock"


def pytest_configure(config: pytest.Config) -> None:
    """Register the marker (``--strict-markers`` is on)."""
    config.addinivalue_line(
        "markers",
        "exclusive_host: counts host processes; runs with no other test running",
    )


@pytest.fixture(autouse=True)
def _host_lock(request: pytest.FixtureRequest) -> Iterator[None]:
    exclusive = request.node.get_closest_marker("exclusive_host") is not None
    with _LOCK.open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        yield
