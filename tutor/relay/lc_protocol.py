# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Request fields of the ``lc_*`` kinds (``DOCS-contract-coach.md``).

Shape checks only. The id field is ``lc_id``, never ``session``: the relay
mirrors a body's ``session`` into ``sessions/<id>/meta``.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from collections.abc import Callable

_LC_ID: Final = re.compile(r"[0-9a-f]{12}", re.ASCII)
SQL_LANGS: Final = ("mysql", "postgresql")
ALGO_LANGS: Final = ("python3", "javascript", "typescript")
LANGS: Final = (*SQL_LANGS, *ALGO_LANGS)
INTENTS: Final = ("chat", "solved")
MAX_PROBLEM: Final = 200
MAX_TITLE: Final = 120
MAX_TEXT: Final = 8000
MAX_CONFIRM: Final = 5
MAX_PROPS: Final = 12
MAX_NAME: Final = 60


def _opt_text(limit: int) -> Callable[[object], str | None]:
    def check(value: object) -> str | None:
        if value is None:
            return None
        if isinstance(value, str) and value.strip() and len(value) <= limit:
            return value
        raise ValueError

    return check


def _text(value: object) -> str:
    if isinstance(value, str) and value.strip() and len(value) <= MAX_TEXT:
        return value
    raise ValueError


def _lc_id(value: object) -> str:
    if isinstance(value, str) and _LC_ID.fullmatch(value):
        return value
    raise ValueError


def _opt_lc_id(value: object) -> str | None:
    return None if value is None else _lc_id(value)


def _lang(value: object) -> str:
    if isinstance(value, str) and value in LANGS:
        return value
    raise ValueError


def _opt_lang(value: object) -> str | None:
    return None if value is None else _lang(value)


def _intent(value: object) -> str:
    if value is None:
        return "chat"
    if isinstance(value, str) and value in INTENTS:
        return value
    raise ValueError


def _name(value: object) -> str:
    if isinstance(value, str) and value.strip() and len(value) <= MAX_NAME:
        return value.strip()
    raise ValueError


def _strings(value: object, *, empty: bool) -> list[str]:
    """A list of names (RTDB drops an empty list: absent = ``[]`` when allowed)."""
    if value is None and empty:
        return []
    if not isinstance(value, list) or len(value) > MAX_PROPS or not (value or empty):
        raise ValueError
    return [_name(v) for v in value]


def _entry(value: object) -> dict[str, Any]:
    given = value if isinstance(value, dict) else {}
    return {
        "name": _name(given.get("name")),
        "aliases": _strings(given.get("aliases"), empty=True),
        "properties": _strings(given.get("properties"), empty=False),
    }


def _confirm(value: object) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, list) and len(value) <= MAX_CONFIRM:
        return [_entry(v) for v in value]
    raise ValueError


FIELDS: Final[dict[str, dict[str, Callable[[object], object]]]] = {
    "lc_list": {},
    "lc_open": {
        "problem": _opt_text(MAX_PROBLEM),
        "statement": _opt_text(MAX_TEXT),
        "title": _opt_text(MAX_TITLE),
        "lang": _opt_lang,
        "lc_id": _opt_lc_id,
    },
    "lc_turn": {"lc_id": _lc_id, "text": _text, "intent": _intent},
    "lc_run": {"lc_id": _lc_id, "lang": _lang, "code": _text},
    "lc_cards": {"lc_id": _lc_id, "confirm": _confirm},
}
