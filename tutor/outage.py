# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Telling "Claude is unavailable" from our own failures, by typed SDK fields.

The CLI reports an outage in fields, never only in prose:

* a ``RateLimitEvent`` whose ``rate_limit_info.status`` is ``rejected`` (its
  ``resets_at`` says until when), or an API error with HTTP 429 / an
  ``AssistantMessage.error`` of ``rate_limit``: ``rate_limit``, never retried;
* an API error with any 5xx ``api_error_status`` (529 is "overloaded"):
  ``overloaded``;
* an ``AssistantMessage.error`` of ``server_error`` (the CLI's "connection
  lost" / "no response"), or a ``terminal_reason`` of ``api_error``, with no
  HTTP status: ``network``.

A turn that produced a successful result is never an outage, whatever a rate
limit event said (overage can still serve it). The same failure arrives as a
raised ``ResultError`` when the CLI exits on it. Overloaded and network get
exactly one retry (the CLI has already backed off on its own); what still
fails is recorded in ``unavailable.jsonl`` and raised as
:class:`ClaudeUnavailableError`. Anything else is not an outage and stays the
caller's ``model_error``, so our own bugs are never hidden behind it.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, Final

from claude_agent_sdk import (
    AssistantMessage,
    RateLimitEvent,
    ResultError,
    ResultMessage,
)

from tutor import unavailable

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

RATE_LIMIT: Final = "rate_limit"
OVERLOADED: Final = "overloaded"
NETWORK: Final = "network"
_TOO_MANY: Final = 429
_SERVER_ERRORS: Final = 500
_logger = logging.getLogger(__name__)


class ClaudeUnavailableError(RuntimeError):
    """Claude cannot answer now; ``resets_at`` (unix s) is when it should again."""

    def __init__(self, reason: str, resets_at: int | None = None) -> None:
        """``reason`` is one of ``unavailable.REASONS``."""
        self.reason, self.resets_at = reason, resets_at
        until = f" until {resets_at}" if resets_at else ""
        super().__init__(f"Claude is unavailable ({reason}){until}")

    def fields(self) -> dict[str, object]:
        """What a client needs to show the outage: ``reason`` and ``resets_at``."""
        return {"reason": self.reason, "resets_at": self.resets_at}


def _reason(status: int | None, error: str | None, terminal: str | None) -> str | None:
    """The outage an API failure's HTTP status / error kind names, if any."""
    if status == _TOO_MANY or error == RATE_LIMIT:
        return RATE_LIMIT
    if status is not None and status >= _SERVER_ERRORS:
        return OVERLOADED
    if status is None and (error == "server_error" or terminal == "api_error"):
        return NETWORK
    return None


def detect(messages: list[Any]) -> ClaudeUnavailableError | None:
    """The outage one turn's messages report; None if it answered or is ours."""
    rejected = False
    resets: int | None = None
    error: str | None = None
    result: ResultMessage | None = None
    for msg in messages:
        if isinstance(msg, RateLimitEvent) and msg.rate_limit_info.status == "rejected":
            rejected, resets = True, msg.rate_limit_info.resets_at
        elif isinstance(msg, AssistantMessage) and msg.error:
            error = msg.error
        elif isinstance(msg, ResultMessage):
            result = msg
    if result is not None and not result.is_error:
        return None
    if rejected:
        return ClaudeUnavailableError(RATE_LIMIT, resets)
    status = result.api_error_status if result else None
    found = _reason(status, error, result.terminal_reason if result else None)
    return None if found is None else ClaudeUnavailableError(found)


def record(
    err: ClaudeUnavailableError, now: float | None = None
) -> ClaudeUnavailableError:
    """Log the outage window; the returned error says when the window ends."""
    at = time.time() if now is None else now
    window = unavailable.record(err.reason, at, err.resets_at)
    _logger.warning("Claude unavailable (%s) until %d", err.reason, window.end)
    return ClaudeUnavailableError(err.reason, window.end)


def from_exit(err: BaseException | None) -> BaseException | None:
    """A CLI that exited on an API outage (``ResultError``), as a recorded one."""
    if not isinstance(err, ResultError):
        return err
    found = _reason(err.api_error_status, None, err.terminal_reason)
    return err if found is None else record(ClaudeUnavailableError(found))


async def retrying[T](turn: Callable[[], Awaitable[T]]) -> T:
    """``turn()``, once more after an overloaded / network failure.

    A rate limit is not retried (it holds until its reset). The outage that
    is finally raised has been recorded.
    """
    try:
        return await turn()
    except ClaudeUnavailableError as err:
        if err.reason == RATE_LIMIT:
            raise record(err) from err
        _logger.warning("Claude %s; retrying the turn once", err.reason)
    try:
        return await turn()
    except ClaudeUnavailableError as err:
        raise record(err) from err


def ensure_available(now: float) -> None:
    """Fail fast while a recorded window covers ``now``: no CLI is spawned."""
    window = unavailable.current(now)
    if window is not None:
        raise ClaudeUnavailableError(window.reason, window.end)
