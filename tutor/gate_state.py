# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Today's tutor progress for the evening gate, read from the signed ledger.

Light on purpose: stdlib plus ``earned_time``, so the gate imports under
``/usr/bin/python3`` without the tutor's venv-only dependencies. Read-only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
import logging
from typing import TYPE_CHECKING, Final

import earned_time

if TYPE_CHECKING:
    from tutor.ledger_io import Paths

_logger: Final = logging.getLogger(__name__)
# What a failed read can raise; anything else is a bug and should surface.
_READ_ERRORS: Final = (OSError, ValueError, TypeError, LookupError)


@dataclass(frozen=True)
class Progress:
    """Minutes tutored today against the day's quota; ``paid`` = reward earned."""

    minutes: int
    quota: int
    paid: bool


def local_today() -> date:
    """Today's date in the machine's zone (the day the ledger rows count for)."""
    return datetime.now(tz=UTC).astimezone().date()


def read_progress(paths: Paths, day: date) -> Progress | None:
    """Today's progress, or ``None`` when the ledger or key cannot be checked.

    ``None`` is "could not check", never "nothing done": the caller keeps the
    gate up (fail closed) and says so. The unit count is the earner's own
    (``credit_units``: minutes scaled to ``max_units`` by the weekday quota), so
    paid here is exactly what earned_time pays on.
    """
    try:
        units = earned_time.credit_units(
            earned_time.TUTOR, paths.ledger, paths.key_file, day
        )
    except _READ_ERRORS:
        _logger.exception("tutor ledger check failed")
        return None
    if units is None:
        _logger.warning("tutor ledger or key unreadable; cannot check today")
        return None
    most = earned_time.TUTOR.max_units or 1
    quota = earned_time.tutor_quota_for(day) or most
    # ``units`` is floor(minutes * most / quota): the ceiling inverts it.
    minutes = min(quota, -(-units * quota // most))
    return Progress(minutes=minutes, quota=quota, paid=units >= most)
