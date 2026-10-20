# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Request failures as the contract's error codes (``DOCS-contract.md`` §4).

The ``error`` text is shown to kuhy; tracebacks stay in the worker log.
``retry`` tells the client the same request may succeed if sent again as a
NEW rid (same ``sent_at``): the done-map answers a resent rid with the
recorded result forever, so a retry is never the same rid.
``claude_unavailable`` also carries ``reason`` and ``resets_at`` (unix s).
"""

from __future__ import annotations

from typing import Final

from claude_agent_sdk import ClaudeSDKError

from tutor.outage import ClaudeUnavailableError
from tutor.session import SessionError

CODES: Final = frozenset(
    {
        "bad_request",
        "not_live",
        "session_live",
        "locked",
        "daily_new_cap",
        "no_card_left",
        "unknown_card",
        "plan_conflict",
        "edit_refused",
        "model_error",
        "claude_unavailable",
        "unknown_prompt",
        "gave_up",
        "worker_error",
    }
)
# Engine ValueError text -> code (gating.py / cardflow.py wording).
_VALUE_CODES: Final = (
    ("locked until", "locked"),
    ("unknown card", "unknown_card"),
    ("no unfinished card", "no_card_left"),
    ("stop the current session first", "session_live"),
)


class RequestError(Exception):
    """A request the worker refuses or failed, with its contract code."""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        retry: bool = False,
        extra: dict[str, object] | None = None,
    ) -> None:
        """``code`` must be one of :data:`CODES` (else ``worker_error``).

        ``extra`` fields join the result node (``claude_unavailable``'s times).
        """
        super().__init__(message)
        self.code = code if code in CODES else "worker_error"
        self.message = message
        self.retry = retry
        self.extra = extra or {}


def _coded(err: BaseException) -> RequestError | None:
    """An outage (itself, or the cause a curriculum error kept), or a coded error."""
    for found in (err, err.__cause__):
        if isinstance(found, ClaudeUnavailableError):
            msg, extra = str(found), found.fields()
            return RequestError(msg, code="claude_unavailable", extra=extra)
    code = getattr(err, "code", None)
    if isinstance(code, str) and code in CODES:  # B2's curriculum RequestError
        return RequestError(
            str(getattr(err, "message", None) or err),
            code=code,
            retry=bool(getattr(err, "retry", False)),
            extra=dict(getattr(err, "extra", None) or {}),
        )
    return None


def classify(err: BaseException) -> RequestError:
    """The contract error for any exception a handler raised."""
    if isinstance(err, RequestError):
        return err
    if (coded := _coded(err)) is not None:
        return coded
    if isinstance(err, (SessionError, ClaudeSDKError, TimeoutError)):
        msg = f"the tutor model failed: {err}"
        return RequestError(msg, code="model_error", retry=True)
    if isinstance(err, ValueError):
        text = str(err)
        found = next((c for key, c in _VALUE_CODES if key in text), "bad_request")
        return RequestError(text, code=found)
    if isinstance(err, RuntimeError) and "no session started" in str(err):
        return RequestError("no session is live", code="not_live")
    return RequestError(f"worker error: {type(err).__name__}", code="worker_error")


def result_of(err: RequestError) -> dict[str, object]:
    """The ``result`` node of a failed request (``at`` added on write)."""
    return {
        **err.extra,
        "ok": False,
        "code": err.code,
        "error": err.message,
        "retry": err.retry,
    }
