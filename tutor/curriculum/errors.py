# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The one error a curriculum request raises: a contract code plus a message.

The relay worker turns it into ``{"ok": false, "code", "error"}``
(``DOCS-contract.md`` §4); ``error`` is shown to kuhy, so it says what to do,
never a traceback.
"""

from __future__ import annotations

from typing import Final

BAD_REQUEST: Final = "bad_request"
LOCKED: Final = "locked"
DAILY_NEW_CAP: Final = "daily_new_cap"
NO_CARD_LEFT: Final = "no_card_left"
UNKNOWN_CARD: Final = "unknown_card"
PLAN_CONFLICT: Final = "plan_conflict"
EDIT_REFUSED: Final = "edit_refused"
MODEL_ERROR: Final = "model_error"
# Claude is rate limited, overloaded or unreachable (``tutor.outage``).
CLAUDE_UNAVAILABLE: Final = "claude_unavailable"
CODES: Final = frozenset(
    {
        BAD_REQUEST,
        "not_live",
        LOCKED,
        DAILY_NEW_CAP,
        NO_CARD_LEFT,
        UNKNOWN_CARD,
        PLAN_CONFLICT,
        EDIT_REFUSED,
        MODEL_ERROR,
        CLAUDE_UNAVAILABLE,
        "gave_up",
        "worker_error",
    }
)


class RequestError(ValueError):
    """A request refused with a contract error code (``DOCS-contract.md`` §4).

    A ``ValueError``, so the routes that already turn ``ValueError`` into a
    400 keep working when the engine raises one.
    """

    def __init__(self, code: str, message: str) -> None:
        """``code`` must be one of :data:`CODES`."""
        if code not in CODES:
            msg = f"unknown error code {code!r}"
            raise ValueError(msg)
        super().__init__(message)
        self.code = code
        self.message = message

    def result(self, at: int) -> dict[str, object]:
        """The request's ``result`` node for this error."""
        return {
            "ok": False,
            "at": at,
            "code": self.code,
            "error": self.message,
            "retry": False,
        }
