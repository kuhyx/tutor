# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Draining client feedback reports into ``feedback.jsonl`` (``DOCS-contract.md`` §6).

Each ``feedback/{fid}`` node is validated like the web page's report, given
the worker's own snapshot of the message it points at, appended locally and
then deleted from RTDB. The fid is stored with the report, so a delete that
failed never records it twice. Feedback never reaches the model.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import TYPE_CHECKING, Any, Final

from tutor import feedback, feedback_snapshot, history, resume
from tutor.relay.protocol import valid_rid
from tutor.relay.rtdb import RtdbError

if TYPE_CHECKING:
    from tutor.relay.context import Wiring

POLL_S: Final = 60.0
_MSG_KEY: Final = re.compile(r"m\d{4}", re.ASCII)
_logger = logging.getLogger(__name__)


def _messages(wiring: Wiring, sid: object) -> list[dict[str, Any]]:
    """The page messages of session ``sid`` (live: the engine's; else replayed)."""
    engine = wiring.engine
    if not isinstance(sid, str):
        return []
    if sid == engine.session_id:
        return engine.messages
    path = history.transcript_path(engine.store.root / "sessions", sid)
    replayed = resume.replay(path) if path else None
    return replayed.conversation.messages if replayed else []


def _index(msg: object) -> int | None:
    """``m0007`` -> 6 (``None`` for anything else)."""
    if isinstance(msg, str) and _MSG_KEY.fullmatch(msg):
        return int(msg[1:]) - 1
    return None


def entry(wiring: Wiring, fid: str, node: object) -> dict[str, Any]:
    """The local report for one RTDB node; Value/TypeError: invalid (dropped)."""
    if not isinstance(node, dict):
        msg = "feedback node is not an object"
        raise TypeError(msg)
    sid = node.get("session")
    messages = _messages(wiring, sid)
    body = {**node, "message_index": _index(node.get("msg"))}
    category, text, index = feedback.validate(body, len(messages))
    out: dict[str, Any] = {
        "category": category,
        "text": text,
        "session_id": sid if isinstance(sid, str) and messages else None,
        "card_id": None,
        "page_url": str(node.get("route") or "")[:500],
        "user_agent": f"relay device {str(node.get('dev') or '?')[:36]}",
        "fid": fid,
    }
    if index is not None:
        out["message_index"] = index
        out["snapshot"] = feedback_snapshot.snapshot(messages, index)
    return out


async def drain(wiring: Wiring) -> int:
    """Move every pending report to ``feedback.jsonl``; returns how many."""
    pending = await wiring.rtdb.get("feedback")
    if not isinstance(pending, dict):
        return 0
    seen = {e.get("fid") for e in await asyncio.to_thread(feedback.load)}
    moved = 0
    for fid, node in sorted(pending.items()):
        if not valid_rid(fid):
            _logger.warning("feedback key %r is not a ULID; ignored", fid[:40])
            continue
        if fid not in seen:
            try:
                await asyncio.to_thread(feedback.record, entry(wiring, fid, node))
                moved += 1
            except (ValueError, TypeError) as err:
                _logger.warning("feedback %s dropped: %s", fid, err)
        await wiring.rtdb.delete(f"feedback/{fid}")
    return moved


async def run(wiring: Wiring) -> None:
    """Drain once a minute, forever."""
    while True:
        try:
            await drain(wiring)
        except (RtdbError, OSError, KeyError) as err:
            _logger.warning("feedback drain failed: %s", err)
        await asyncio.sleep(POLL_S)
