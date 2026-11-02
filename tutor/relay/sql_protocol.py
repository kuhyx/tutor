# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Request fields of the ``sql_*`` kinds (``DOCS-contract-sql.md``).

Shape checks only; the engine decides whether a drill exists. RTDB drops
empty lists, so an absent list field means ``[]``.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from collections.abc import Callable

_ID: Final = re.compile(r"[A-Za-z0-9_.-]{1,64}", re.ASCII)
TOPICS: Final = (
    "basics",
    "pivot",
    "dates",
    "number-format",
    "joins-null",
    "group-having",
    "window",
    "strings",
)
DIFFICULTIES: Final = ("easy", "medium", "hard")
MAX_SQL: Final = 8000
MAX_ROWS: Final = 60
MAX_COLS: Final = 30
MAX_CELL: Final = 200
MAX_HISTORY: Final = 10
MAX_HINT: Final = 500
MAX_RESULT_ROWS: Final = 20


def _id(value: object) -> str:
    if isinstance(value, str) and _ID.fullmatch(value):
        return value
    raise ValueError


def _sql(value: object) -> str:
    if isinstance(value, str) and value.strip() and len(value) <= MAX_SQL:
        return value
    raise ValueError


def _opt_sql(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str) and len(value) <= MAX_SQL:
        return value
    raise ValueError


def _cell(value: object) -> str:
    if isinstance(value, str) and len(value) <= MAX_CELL:
        return value
    raise ValueError


def _grid(value: object) -> list[list[str]]:
    """Rows of string cells; absent = no rows (RTDB drops the empty list)."""
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > MAX_ROWS:
        raise ValueError
    rows: list[list[str]] = []
    for row in value:
        if not isinstance(row, list) or len(row) > MAX_COLS:
            raise ValueError
        rows.append([_cell(c) for c in row])
    return rows


def _history(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list) and len(value) <= MAX_HISTORY:
        for item in value:
            if not (isinstance(item, str) and len(item) <= MAX_HINT):
                raise ValueError
        return [str(v) for v in value]
    raise ValueError


def _last_result(value: object) -> dict[str, Any] | None:
    """The slice of a ``sql_run`` result a hint may read (all else dropped)."""
    if value is None:
        return None
    given = value if isinstance(value, dict) else None
    if given is None:
        raise ValueError
    out: dict[str, Any] = {
        k: given[k] for k in ("ok", "match") if isinstance(given.get(k), bool)
    }
    if isinstance(given.get("error"), str):
        out["error"] = given["error"][:MAX_SQL]
    for key in ("columns", "rows", "cell_diff"):
        if isinstance(given.get(key), list):
            out[key] = given[key][:MAX_RESULT_ROWS]
    return out


def _topic(value: object) -> str:
    if isinstance(value, str) and value in TOPICS:
        return value
    raise ValueError


def _difficulty(value: object) -> str:
    if value is None:
        return "medium"
    if isinstance(value, str) and value in DIFFICULTIES:
        return value
    raise ValueError


FIELDS: Final[dict[str, dict[str, Callable[[object], object]]]] = {
    "sql_list": {},
    "sql_get": {"id": _id},
    "sql_run": {"id": _id, "sql": _sql},
    "sql_predict": {"id": _id, "grid": _grid},
    "sql_hint": {
        "id": _id,
        "sql": _opt_sql,
        "last_result": _last_result,
        "history": _history,
    },
    "sql_generate": {"topic": _topic, "difficulty": _difficulty},
}
