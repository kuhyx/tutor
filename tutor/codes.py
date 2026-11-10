# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Machine codes beside the sentences the server sends (``DOCS-contract.md`` §4a).

The app is text-free: it paints a glyph per code and keeps the sentence as
the spoken label. Each surface has one closed vocabulary here; anything not
in it travels as :data:`OTHER` (the app's generic glyph), and adding a value
is a deliberate change to ``contract/codes.json``, which the Dart mirror
(``app/lib/model/codes.dart``) is tested against too. ``test_codes`` pins
each set to what the server actually emits.
"""

from __future__ import annotations

from typing import Final

from claude_agent_sdk import ClaudeSDKError

from tutor.outage import NETWORK, OVERLOADED, RATE_LIMIT, ClaudeUnavailableError
from tutor.session import SessionError

OTHER: Final = "other"

# A failed request's ``code`` (``relay.errors.CODES`` plus ``other``).
RELAY_CODE: Final = frozenset(
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
        "focus_refused",
        "model_error",
        "claude_unavailable",
        "unknown_prompt",
        "gave_up",
        "worker_error",
        OTHER,
    }
)
# Claude's outage reasons (``unavailable.REASONS``): ``Unavailable.reason``.
UNAVAILABLE_REASON: Final = frozenset({RATE_LIMIT, OVERLOADED, NETWORK})
# The coach could not fetch the problem: kuhy pastes its statement.
PASTE_STATEMENT: Final = "paste_statement"
# A failed result's ``reason``: ``paste_statement`` (``bad_request``) or the
# outage's (``claude_unavailable``).
FAIL_REASON: Final = frozenset({PASTE_STATEMENT, OTHER} | UNAVAILABLE_REASON)
# ``notice_kinds[i]`` names what ``notices[i]`` (a card edit) did.
REMOVED: Final = "removed"
ADDED: Final = "added"
MNEMONIC_SET: Final = "mnemonic_set"
MNEMONIC_CLEARED: Final = "mnemonic_cleared"
SPLIT: Final = "split"
UPDATED: Final = "updated"
NOTICE_KIND: Final = frozenset(
    {REMOVED, ADDED, MNEMONIC_SET, MNEMONIC_CLEARED, SPLIT, UPDATED, OTHER}
)
# ``clock.paused_reason`` is already a fixed sentence; the app keys on it.
PAUSE_REASON: Final = {
    "low_effort": "low-effort reply",
    "stalled": "no reply for 10 min",
}
# ``error_kind`` beside a generation / request ``error``.
CLAUDE_LIMIT: Final = "claude_limit"
MODEL_FAILED: Final = "model_failed"
SOURCES_MISSING: Final = "sources_missing"
TOO_FEW_CARDS: Final = "too_few_cards"
BAD_REQUEST: Final = "bad_request"
_OUTAGE_KIND: Final = {
    RATE_LIMIT: CLAUDE_LIMIT,
    OVERLOADED: "claude_overloaded",
    NETWORK: "claude_network",
}
ERROR_KIND: Final = frozenset(
    {MODEL_FAILED, SOURCES_MISSING, TOO_FEW_CARDS, BAD_REQUEST, OTHER}
    | set(_OUTAGE_KIND.values())
)
# The worker's phases, in order (``relay.claims.PHASES``).
RELAY_PHASE: Final = ("claimed", "thinking", "images", "checking_images", "publishing")
_CODE_KIND: Final = {"model_error": MODEL_FAILED, "bad_request": BAD_REQUEST}


def closed(vocab: frozenset[str], value: object) -> str:
    """``value`` if it is in ``vocab``, else :data:`OTHER`."""
    return value if isinstance(value, str) and value in vocab else OTHER


def kind_of(code: object, reason: object = None) -> str:
    """The ``error_kind`` of a contract ``code`` (and an outage's ``reason``)."""
    if code == "claude_unavailable":
        return _OUTAGE_KIND.get(str(reason), OTHER)
    return _CODE_KIND.get(str(code), OTHER)


def error_kind(err: BaseException) -> str:
    """The ``error_kind`` of an exception, by its type, never its message.

    An outage wins (itself, or the cause a ``RequestError`` kept); then the
    model's own failures; then a coded error's ``code``.
    """
    for found in (err, err.__cause__):
        if isinstance(found, ClaudeUnavailableError):
            return _OUTAGE_KIND.get(found.reason, OTHER)
    if isinstance(err, (SessionError, ClaudeSDKError, TimeoutError)):
        return MODEL_FAILED
    code = getattr(err, "code", None)
    extra = getattr(err, "extra", None)
    reason = extra.get("reason") if isinstance(extra, dict) else None
    return kind_of(code, reason)


def vocabulary() -> dict[str, object]:
    """Every vocabulary in ``contract/codes.json``'s shape (sets sorted)."""
    return {
        "relay_code": sorted(RELAY_CODE),
        "fail_reason": sorted(FAIL_REASON),
        "notice_kind": sorted(NOTICE_KIND),
        "pause_reason": dict(PAUSE_REASON),
        "error_kind": sorted(ERROR_KIND),
        "relay_phase": list(RELAY_PHASE),
        "unavailable_reason": sorted(UNAVAILABLE_REASON),
    }
