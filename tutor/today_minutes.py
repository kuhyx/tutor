# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Today's own minutes, apart from carry: the Home counter (part e79be0be-1).

Carry prepays the day's quota in the morning (``DOCS-contract-carry.md``),
so kuhy's own minutes went to the bank and the quota counter never moved
(2026-11-26: "I did anki cards on my phone but got no bonus time"). The
stats node therefore also says what kuhy earned himself today:
``own_minutes``, the verified ``credit`` minutes that are not a carry row,
and ``lc_minutes``, the ``leetcode_theory`` ones leetcode-guard pays.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, NamedTuple

from tutor.credit import local_day
from tutor.ledger_io import LedgerError, default_paths, read_key, read_rows
from tutor.ledger_pay import CREDIT, LC_CREDIT, paying

if TYPE_CHECKING:
    from tutor.ledger_io import Paths

log = logging.getLogger(__name__)
CARRY_PREFIX = "carry-"  # ``carry.carry_row``'s entry ids


class Own(NamedTuple):
    """Today's own tutor minutes and LeetCode minutes."""

    own: int
    leetcode: int


def today(moment: float, *, paths: Paths | None = None) -> Own:
    """Minutes earned on ``moment``'s local day; zeros when the ledger is unreadable."""
    where = paths or default_paths()
    key = read_key(where.key_file)
    try:
        rows = read_rows(where.ledger) if key else []
    except LedgerError as err:  # the counter shows 0 rather than failing stats
        log.warning("ledger unreadable, own minutes shown as 0: %s", err)
        rows = []
    if not key:
        return Own(0, 0)
    day = local_day(moment)[0]

    def total(kind: str, *, skip_carry: bool) -> int:
        paid = paying(rows, key, {kind})
        return sum(
            minutes
            for entry, (ended, minutes) in paid.items()
            if local_day(ended)[0] == day
            and not (skip_carry and entry.startswith(CARRY_PREFIX))
        )

    return Own(total(CREDIT, skip_carry=True), total(LC_CREDIT, skip_carry=False))
