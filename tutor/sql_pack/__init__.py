# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Hand-written SQL drill pack for the timed MySQL test.

Every spec is plain data; ``sql-pack`` saves them through
``sql_drills.save_generated``, which runs each reference query on a fresh
MySQL 8 and refuses an empty, failing or non-deterministic one. Expected
outputs therefore always come from the engine, never from this text.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from tutor.sql_pack import dates, groups, joins, numbers, pivot, strings, window

if TYPE_CHECKING:
    from tutor.sql_pack.spec import Spec

SPECS: Final[tuple[Spec, ...]] = (
    *pivot.SPECS,
    *dates.SPECS,
    *numbers.SPECS,
    *joins.SPECS,
    *groups.SPECS,
    *window.SPECS,
    *strings.SPECS,
)
