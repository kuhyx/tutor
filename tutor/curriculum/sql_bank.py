# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The SQL card bank: guided-lesson concept title -> the cards it earns."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from tutor.curriculum.sql_bank_group import (
    FORMAT_CARDS,
    HAVING_CARDS,
    PIVOT_CARDS,
    QUOTE_CARDS,
)
from tutor.curriculum.sql_bank_null import JOIN_CARDS, NULL_CARDS

if TYPE_CHECKING:
    from tutor.curriculum.sql_card_spec import CardSpec

_NUMBERS: Final = tuple(c for c in FORMAT_CARDS if not c.key.startswith("date-"))
BANK: Final[dict[str, tuple[CardSpec, ...]]] = {
    "NULL comparisons": NULL_CARDS,
    "JOIN ON vs WHERE": JOIN_CARDS[:2],
    "anti-join": JOIN_CARDS[2:],
    "WHERE vs HAVING": HAVING_CARDS,
    "pivot with SUM(CASE WHEN)": PIVOT_CARDS,
    "date bucketing": tuple(c for c in FORMAT_CARDS if c.key.startswith("date-")),
    "integer division and rounding": _NUMBERS,
    "CONCAT, percentages and formatting": QUOTE_CARDS,
}
