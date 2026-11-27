# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Test modules are imported in the zone the tests run in.

``tutor_sandbox`` pins ``TZ=Europe/Warsaw`` for every test, but a constant a
test module computes at import (``NOW_LOCAL``: an epoch read as local time)
is evaluated at collection, before any fixture. On a UTC runner (CI) that
constant was an hour off the value the code computed under the fixture, and
the suite passed only on a Warsaw machine. The root ``conftest.py`` pins the
zone before collection, so import time and test time agree everywhere.
"""

from __future__ import annotations

from datetime import UTC, datetime
import time

from tutor.tests._focus_support import NOW
from tutor.tests._interview_support import NOW_LOCAL

# Read while this module is imported, i.e. during collection.
IMPORT_ZONE = time.tzname


def test_modules_are_imported_in_the_test_zone() -> None:
    assert IMPORT_ZONE == ("CET", "CEST")
    assert time.tzname == IMPORT_ZONE


def test_an_import_time_local_stamp_matches_one_read_in_a_test() -> None:
    now = datetime.fromtimestamp(NOW, tz=UTC).astimezone().replace(tzinfo=None)
    assert now == NOW_LOCAL
