# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""A session's RTDB projection, rebuilt from its transcript (``DOCS-contract.md`` §6).

The jsonl transcript is the commit point and ``resume.replay`` /
``history.session_view`` already rebuild everything the page shows from it,
so the projection is built the same way for the live session and for a
migrated one. ``rev`` is the transcript's event count: it only grows, needs
no state of its own and tells a stale RTDB copy from a current one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import logging
import time
from typing import TYPE_CHECKING, Any, Final

from tutor import history, resume, unit_credit
from tutor.clock import REPLY_TIMEOUT
from tutor.relay import media_out
from tutor.relay.claims import ms

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from tutor.conversation import Conversation

DEFAULT_SUBJECT: Final = "automation"
_TUTOR_KEYS: Final = (
    "text",
    "questions",
    "choices",
    "low_effort",
    "check",
    "check_result",
)
_TUTOR_FLAGS: Final = ("mastered_new", "card_done")
_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Sources:
    """What a projection reads besides the transcript."""

    view: history.View
    now: float
    dev_of: Callable[[str], str | None]  # rid -> device
    resolve_url: Callable[[str], str | None]  # Commons page -> thumbnail
    diagram_cache: Path | None = None


@dataclass(frozen=True)
class SessionDoc:
    """Everything published for one session."""

    sid: str
    rev: int
    meta: dict[str, Any]
    msgs: dict[str, Any]
    receipts: dict[str, Any]
    index: dict[str, Any]


def _events(path: Path) -> list[dict[str, Any]]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except ValueError as err:  # a line cut short by a kill
            _logger.warning("%s: unreadable line skipped: %s", path.name, err)
            continue
        if isinstance(event, dict):
            out.append(event)
    return out


def _t(event: dict[str, Any]) -> int:
    if "t" in event:
        return ms(float(event["t"]))
    return ms(datetime.fromisoformat(event["logged_at"]).timestamp())


def _times(events: list[dict[str, Any]]) -> tuple[list[int], list[tuple[str, int]]]:
    """Tutor message times; (rid, time) per learner message, paired as replay does."""
    tutor: list[int] = []
    learner: list[tuple[str, int]] = []
    waiting: dict[str, Any] | None = None  # a learner event not yet answered
    for event in events:
        match event.get("type"):
            case "learner":
                waiting = event
            case "tutor":
                if waiting is not None:
                    learner.append((str(waiting.get("msg_id") or ""), _t(waiting)))
                tutor.append(_t(event))
                waiting = None
            case "next_card" | "stop":
                waiting = None
            case _:
                pass
    return tutor, learner


def _tutor_msg(raw: dict[str, Any], at: int | None, src: Sources) -> dict[str, Any]:
    msg: dict[str, Any] = {"role": "tutor", **{k: raw.get(k) for k in _TUTOR_KEYS}}
    msg["images"] = [
        media_out.image(i, src.resolve_url) for i in raw.get("images") or []
    ]
    msg["diagrams"] = media_out.diagrams_of(raw, src.diagram_cache)
    msg.update({k: raw[k] for k in _TUTOR_FLAGS if raw.get(k)})
    msg["at"] = at
    return msg


def messages(
    conv: Conversation, events: list[dict[str, Any]], src: Sources
) -> list[dict[str, Any]]:
    """The page messages shaped for RTDB, each with its time (and rid, device)."""
    tutor, learner = _times(events)
    out: list[dict[str, Any]] = []
    for raw in conv.messages:
        role = raw.get("role")
        if role == "tutor":
            out.append(_tutor_msg(raw, tutor.pop(0) if tutor else None, src))
        elif role == "learner":
            rid, at = learner.pop(0) if learner else ("", None)
            node = {"role": "learner", "text": raw.get("text", ""), "at": at}
            if rid:
                node.update(rid=rid, dev=src.dev_of(rid))
            out.append(node)
        else:
            out.append({k: raw.get(k) for k in ("role", "text", "card_id")})
    return out


def started_ms(sid: str) -> int:
    """The session id's local start time (``YYYYMMDD-HHMMSS``) in unix ms."""
    return ms(time.mktime(time.strptime(sid[:15], "%Y%m%d-%H%M%S")))


def _meta(
    conv: Conversation, msgs: list[dict[str, Any]], rev: int, src: Sources, subject: str
) -> dict[str, Any]:
    snap = conv.clock.snapshot(src.now)
    last = msgs[-1] if msgs else {}
    waiting = not conv.stopped and last.get("role") == "tutor"
    return {
        "subject": subject,
        "card": {
            "id": conv.card_id,
            "front": src.view.fronts.get(conv.card_id, conv.card_id),
        },
        "started": started_ms(conv.session_id),
        "stopped": conv.stopped,
        "card_done": conv.card_done,
        "check_open": conv.check.open,
        "n": len(msgs),
        "rev": rev,
        "clock": {
            "active_seconds": snap["active_seconds"],
            "paused_reason": snap["paused_reason"],
            "awaiting_since": last.get("at") if waiting else None,
            "reply_timeout_s": int(REPLY_TIMEOUT),
        },
        "credited_minutes": unit_credit.paid_minutes(conv.receipts),
        "busy": None,
    }


def _index(listed: dict[str, Any], rev: int, subject: str) -> dict[str, Any]:
    sid = listed["session_id"]
    return {
        "started": f"{sid[:4]}-{sid[4:6]}-{sid[6:8]} {sid[9:11]}:{sid[11:13]}",
        "subject": subject,
        "cards": listed["cards"],
        "active_minutes": int(listed["active_seconds"] // 60),
        "credited_minutes": listed["credited_minutes"],
        "stopped": listed["stopped"],
        "auto_archived": listed["auto_archived"],
        "rev": rev,
    }


def key(prefix: str, index: int) -> str:
    """``m0001`` / ``r0001``: never a bare number (RTDB would make an array)."""
    return f"{prefix}{index:04d}"


def build(sessions_dir: Path, sid: str, src: Sources) -> SessionDoc | None:
    """The projection of session ``sid``, or ``None`` (no such or empty session)."""
    path = history.transcript_path(sessions_dir, sid)
    replayed = resume.replay(path) if path else None
    listed = history.session_view(sessions_dir, sid, src.view)
    if path is None or replayed is None or listed is None:
        return None
    events = _events(path)
    start = next((e for e in events if e.get("type") == "start"), {})
    subject = str(start.get("subject") or DEFAULT_SUBJECT)
    conv = replayed.conversation
    msgs = messages(conv, events, src)
    rev = len(events)
    return SessionDoc(
        sid=sid,
        rev=rev,
        meta=_meta(conv, msgs, rev, src, subject),
        msgs={key("m", i): m for i, m in enumerate(msgs, 1)},
        receipts={key("r", i): r for i, r in enumerate(conv.receipts, 1)},
        index=_index(listed, rev, subject),
    )


def transcript_rev(sessions_dir: Path, sid: str) -> int:
    """The local rev of ``sid`` (its event count; 0 when absent)."""
    path = history.transcript_path(sessions_dir, sid)
    return len(_events(path)) if path else 0
