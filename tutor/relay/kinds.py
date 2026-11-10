# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The ``kind`` of a failed request: one flat name per case (``DOCS-relay-kinds.md``).

The app draws a failed or blocked result from its ``kind`` (a glyph and a
calm or error tint), never from the ``error`` sentence. A code maps to one
kind; ``bad_request``'s ``reason`` and ``no_card_left`` / ``locked``'s
``next`` split it further. ``claude_unavailable``'s ``reason`` (rate limit,
overloaded, network) does not: the app shows one outage cue and switches to
the drill either way. This is the result's ``kind``, not the request's.

``contract/relay_kinds.json`` is generated from :data:`CASES`
(``scripts/gen_relay_kinds.py``); a test fails when the two drift.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Final, NamedTuple

if TYPE_CHECKING:
    from collections.abc import Mapping


class Case(NamedTuple):
    """One wire case: ``code`` plus an optional ``reason`` or ``next``."""

    code: str
    kind: str
    reason: str | None = None
    next: str | None = None


# Order is the golden file's order: the plain code first, then its splits.
CASES: Final = (
    Case("bad_request", "err_bad_request"),
    Case("bad_request", "refused_paste_statement", reason="paste_statement"),
    Case("not_live", "err_not_live"),
    Case("session_live", "err_session_live"),
    Case("locked", "blocked_locked"),
    Case("locked", "blocked_locked_review", next="review_module"),
    Case("daily_new_cap", "blocked_cap"),
    Case("no_card_left", "blocked_no_card_none"),
    Case("no_card_left", "blocked_no_card_review", next="review_module"),
    Case("no_card_left", "blocked_no_card_due", next="reviews_due"),
    Case("unknown_card", "err_unknown_card"),
    Case("plan_conflict", "err_plan_conflict"),
    Case("edit_refused", "err_edit_refused"),
    Case("focus_refused", "err_focus_refused"),
    Case("model_error", "err_model"),
    Case("claude_unavailable", "outage_claude"),
    Case("unknown_prompt", "err_unknown_prompt"),
    Case("gave_up", "err_gave_up"),
    Case("worker_error", "err_worker"),
)
WORKER_ERROR: Final = "err_worker"
KINDS: Final = tuple(dict.fromkeys(c.kind for c in CASES))
_PLAIN: Final = MappingProxyType(
    {c.code: c.kind for c in CASES if c.reason is None and c.next is None}
)
_BY_REASON: Final[Mapping[tuple[str, object], str]] = MappingProxyType(
    {(c.code, c.reason): c.kind for c in CASES if c.reason is not None}
)
_BY_NEXT: Final[Mapping[tuple[str, object], str]] = MappingProxyType(
    {(c.code, c.next): c.kind for c in CASES if c.next is not None}
)


def kind_of(code: str, reason: object = None, next_step: object = None) -> str:
    """The kind of ``code``; an unknown code is a worker error.

    A non-string ``reason`` / ``next`` splits nothing (and is never hashed).
    """
    by_reason = _BY_REASON.get((code, reason)) if isinstance(reason, str) else None
    by_next = _BY_NEXT.get((code, next_step)) if isinstance(next_step, str) else None
    found = by_reason or by_next
    return found or _PLAIN.get(code, WORKER_ERROR)


def kind_of_node(code: str, extra: dict[str, object]) -> str:
    """The kind of a result node's ``code`` plus its flat ``extra`` fields."""
    return kind_of(code, extra.get("reason"), extra.get("next"))


def golden_rows() -> list[dict[str, str]]:
    """Every case as the contract file lists it (``reason``/``next`` if set)."""
    return [
        {
            "code": c.code,
            **({"reason": c.reason} if c.reason else {}),
            **({"next": c.next} if c.next else {}),
            "kind": c.kind,
        }
        for c in CASES
    ]


def golden(phases: tuple[str, ...]) -> dict[str, object]:
    """The contract file's content: every case, and the claim phases."""
    return {"cases": golden_rows(), "phases": list(phases)}
