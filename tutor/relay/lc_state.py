# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""One coach session's stored state and its wire view (``DOCS-contract-coach.md``)."""

from __future__ import annotations

import json
import logging
import secrets
from typing import TYPE_CHECKING, Any, Final

from tutor.relay.errors import RequestError
from tutor.relay.lc_checks import BUDGET, MAX_TRIES
from tutor.relay.lc_protocol import ALGO_LANGS, SQL_LANGS
from tutor.store import data_dir

if TYPE_CHECKING:
    from pathlib import Path

_logger = logging.getLogger(__name__)
KEEP_THREAD: Final = 120
KEEP_RECENT: Final = 20
MODEL: Final = "sonnet"
type State = dict[str, Any]


def _path(lc_id: str) -> Path:
    return data_dir() / "lc_sessions" / f"{lc_id}.json"


def fresh(problem: dict[str, Any], lang: str, now_ms: int) -> tuple[str, State]:
    """A new session; ``problem`` holds slug, title, difficulty, kind, statement."""
    state: State = {
        **problem,
        "lang": lang,
        "phase": "gate",
        "gate": {"tries": 0, "forced": False, "open": False},
        "turns": 0,
        "rung": -1,
        "revealed": False,
        "ran_ok": False,
        "failed": False,
        "code_seen": False,
        "confused": 0,
        "last_code": "",
        "last_table": "",
        "belief": "",
        "exit": {"step": "explain", "tries": 0},
        "rungs": [],
        "reqs": [],
        "thread": [],
        "created_ms": now_ms,
        "updated_ms": now_ms,
    }
    return secrets.token_hex(6), state


def load(lc_id: str) -> State:
    """The stored session, or ``bad_request`` for an unknown id."""
    try:
        state = json.loads(_path(lc_id).read_text(encoding="utf-8"))
    except OSError, ValueError:
        msg = f"unknown coach session {lc_id!r}"
        raise RequestError(msg, code="bad_request") from None
    if not isinstance(state, dict):
        msg = f"unknown coach session {lc_id!r}"
        raise RequestError(msg, code="bad_request")
    return state


def save(lc_id: str, state: State, now_ms: int) -> None:
    """Write the session atomically."""
    state["thread"] = state["thread"][-KEEP_THREAD:]
    state["updated_ms"] = now_ms
    path = _path(lc_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state), encoding="utf-8")
    tmp.replace(path)


def recent() -> list[dict[str, Any]]:
    """The newest sessions, for ``lc_list``."""
    folder = data_dir() / "lc_sessions"
    rows: list[dict[str, Any]] = []
    for path in folder.glob("*.json") if folder.is_dir() else ():
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
            rows.append(
                {
                    "lc_id": path.stem,
                    "slug": state["slug"],
                    "title": state["title"],
                    "phase": state["phase"],
                    "updated_ms": state["updated_ms"],
                }
            )
        except OSError, ValueError, KeyError:
            _logger.warning("coach session %s is unreadable", path.name)
            continue
    return sorted(rows, key=lambda r: -r["updated_ms"])[:KEEP_RECENT]


def say(state: State, *, mine: bool, md: str) -> None:
    """Append one chat entry."""
    state["thread"].append({"mine": mine, "md": md})


def langs_of(state: State) -> tuple[str, ...]:
    """The languages this session's kind of problem is solved in."""
    return SQL_LANGS if state["kind"] == "sql" else ALGO_LANGS


def budget(state: State) -> int:
    """The coach-turn budget of this problem's difficulty."""
    return BUDGET.get(str(state["difficulty"]), BUDGET["medium"])


def view(state: State) -> dict[str, Any]:
    """The ``State`` object of the wire."""
    gate, limit = state["gate"], budget(state)
    out: dict[str, Any] = {
        "phase": state["phase"],
        "gate": {
            "kind": "shape" if state["kind"] == "sql" else "req",
            "tries": gate["tries"],
            "max": MAX_TRIES,
            "open": gate["open"],
            "forced": gate["forced"],
        },
        "turns": {
            "used": state["turns"],
            "budget": limit,
            "over": state["turns"] >= limit,
        },
        "rung": f"H{state['rung']}" if state["rung"] >= 0 else None,
        "revealed": state["revealed"],
        "ran_ok": state["ran_ok"],
        "exit": {"step": state["exit"]["step"], "tries": state["exit"]["tries"]},
    }
    if state["belief"]:
        out["exit"]["belief"] = state["belief"]
    return out
