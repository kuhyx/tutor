# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The request fields of the kinds that live outside ``protocol.KINDS``' core."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from tutor.relay.focus_protocol import FIELDS as FOCUS_FIELDS
from tutor.relay.lc_protocol import FIELDS as LC_FIELDS
from tutor.relay.mock_protocol import FIELDS as MOCK_FIELDS
from tutor.relay.plan_protocol import FIELDS as PLAN_FIELDS
from tutor.relay.sql_protocol import FIELDS as SQL_FIELDS

if TYPE_CHECKING:
    from collections.abc import Callable

FIELDS: Final[dict[str, dict[str, Callable[[object], object]]]] = {
    **FOCUS_FIELDS,
    **SQL_FIELDS,
    **LC_FIELDS,
    **MOCK_FIELDS,
    **PLAN_FIELDS,
}
