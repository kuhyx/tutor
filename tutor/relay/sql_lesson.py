# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``sql_lesson_turn``: a guided Socratic lesson, the engine as ground truth."""

from __future__ import annotations

import asyncio
import copy
import json
import logging
import secrets
from typing import TYPE_CHECKING, Any, Final

from tutor import outage
from tutor.curriculum.modelcall import ask_model
from tutor.relay import sql_lesson_prompt as prompt
from tutor.relay.errors import RequestError
from tutor.relay.sql import Json, engine_call, heartbeat, wire
from tutor.relay.sql_lesson_plan import PLAN
from tutor.store import data_dir

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.relay.context import RequestContext

_logger = logging.getLogger(__name__)
TRIES: Final = 3
KEEP_HISTORY: Final = 20
KEEP_THREAD: Final = 120


def _path(lesson_id: str) -> Path:
    return data_dir() / "sql_lessons" / f"{lesson_id}.json"


def _load(lesson_id: str, topic: str) -> dict[str, Any]:
    try:
        state = json.loads(_path(lesson_id).read_text(encoding="utf-8"))
    except OSError, ValueError:
        msg = f"unknown lesson {lesson_id!r}"
        raise RequestError(msg, code="bad_request") from None
    if not isinstance(state, dict) or state.get("topic") != topic:
        msg = f"lesson {lesson_id!r} is not a {topic!r} lesson"
        raise RequestError(msg, code="bad_request")
    state.setdefault("thread", [])  # lessons stored before the thread existed
    return state


def _save(lesson_id: str, state: dict[str, Any]) -> None:
    state["history"] = state["history"][-KEEP_HISTORY:]
    state["thread"] = state["thread"][-KEEP_THREAD:]
    path = _path(lesson_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state), encoding="utf-8")
    tmp.replace(path)


def _fresh(topic: str) -> dict[str, Any]:
    return {
        "topic": topic,
        "index": 0,
        "phase": "teach",
        "checks_left": 0,
        "turn": 0,
        "pending": None,
        "history": [],
        "thread": [],
    }


def _dataset(state: dict[str, Any]) -> str:
    plan = PLAN[state["topic"]]
    return plan[min(int(state["index"]), len(plan) - 1)].dataset


async def _tables(state: dict[str, Any]) -> dict[str, Json]:
    dataset = _dataset(state)
    got = wire(await engine_call(lambda sd: lambda: sd.get_drill(dataset), dataset))
    return dict(got["tables"])


async def _real_output(state: dict[str, Any], query: str) -> Json:
    dataset = _dataset(state)
    return wire(await engine_call(lambda sd: lambda: sd.run(dataset, query), dataset))


async def _ask(state: dict[str, Any], answer: str | None) -> dict[str, Json]:
    """One valid model turn whose query ran; the real rows are in ``rows``."""
    tables, note, pending = await _tables(state), "", state["pending"]
    for _ in range(TRIES):
        text = prompt.build(state, tables, answer, note)
        raw = await asyncio.to_thread(ask_model, prompt.SYSTEM, text, prompt.SCHEMA)
        if (why := prompt.problem(raw, answered=answer is not None)) is None:
            turn = prompt.clean(raw)
            ran = await _real_output(state, turn["query"])
            why = _rejection(turn, ran, pending) or prompt.missing_backref(
                turn["question_md"], _earlier(state)
            )
        if why is None:
            return {**turn, "rows": ran["rows"], "columns": ran["columns"]}
        _logger.warning("lesson turn rejected: %s", why)
        note = f"\n\nYour previous reply was rejected: {why}. Fix it."
    msg = "the model gave no valid lesson turn; try again"
    raise RequestError(msg, code="model_error", retry=True)


def _earlier(state: dict[str, Any]) -> list[str]:
    queries = [e["query"] for e in state["history"]]
    return queries + ([state["pending"]["query"]] if state["pending"] else [])


def _rejection(turn: dict[str, Json], ran: Json, pending: Json) -> str | None:
    if not ran["ok"]:
        return f"your query failed in MySQL ({ran['error']}); write a valid one"
    if not ran["rows"]:
        return "your query returns no rows; use one with a non-empty result"
    if prompt.leaked(turn["question_md"], ran["rows"]):
        return "question_md spells out the query's result; show the query only"
    hidden = pending["rows"] if pending and turn["verdict"] != "correct" else []
    if prompt.leaked(turn["feedback_md"], hidden):
        return "feedback_md reveals the previous result before a correct answer"
    return None


def _pending(turn: dict[str, Json]) -> dict[str, Json]:
    keys = ("question_md", "query", "rows", "columns")
    return {k: turn[k] for k in keys}


def _grade(state: dict[str, Any], turn: dict[str, Json], answer: str) -> dict[str, Any]:
    """Apply the model's verdict to ``state``; the fields the client shows."""
    before = state["pending"]
    state["history"].append(
        {
            "query": before["query"],
            "rows": before["rows"],
            "answer": answer,
            "verdict": turn["verdict"],
        }
    )
    right = turn["verdict"] == "correct"
    shown: dict[str, Any] = {"feedback_md": turn["feedback_md"], "advanced": False}
    if right:
        shown["result"] = {"columns": before["columns"], "rows": before["rows"]}
    if state["phase"] == "teach" and right and turn["mastered"]:
        state["phase"], state["checks_left"] = "check", prompt.MIN_CHECKS
        shown["summary_md"] = turn["summary_md"]
    elif state["phase"] == "check" and right:
        state["checks_left"] -= 1
        shown["advanced"] = state["checks_left"] == 0
    elif state["phase"] == "check":
        state["phase"], state["checks_left"] = "teach", 0
    return shown


def _extend_thread(
    state: dict[str, Any], answer: str | None, shown: dict[str, Any]
) -> None:
    """Append what the learner and the tutor just said, as the chat shows it."""
    thread = state["thread"]
    if answer is not None:
        thread.append({"mine": True, "md": answer})
    for key in ("feedback_md", "result", "summary_md"):
        if shown.get(key):
            thread.append(
                {"mine": False, ("grid" if key == "result" else "md"): shown[key]}
            )
    if state["pending"] is not None:
        thread.append({"mine": False, "md": state["pending"]["question_md"]})


def _progress(state: dict[str, Any]) -> dict[str, Json]:
    plan = PLAN[state["topic"]]
    return {
        "concept": plan[min(state["index"], len(plan) - 1)].title,
        "index": state["index"],
        "total": len(plan),
        "phase": state["phase"],
        "checks_left": state["checks_left"],
    }


async def _view(
    lesson_id: str, state: dict[str, Any], shown: dict[str, Any]
) -> dict[str, Json]:
    out: dict[str, Json] = {
        "lesson_id": lesson_id,
        "topic": state["topic"],
        "turn": state["turn"],
        "progress": _progress(state),
        "tables": await _tables(state),
    }
    if state["pending"] is not None:
        out["question_md"] = state["pending"]["question_md"]
    for key in ("feedback_md", "summary_md", "result"):
        if shown.get(key):
            out[key] = shown[key]
    if state["pending"] is None:
        out["done"] = True
    return out


async def sql_lesson_turn(ctx: RequestContext) -> Json:
    """Start, resume or advance a guided lesson (``DOCS-contract-sql.md``)."""
    topic, given, answer = ctx.body["topic"], ctx.body["lesson_id"], ctx.body["answer"]
    if given is None:
        lesson_id, state = secrets.token_hex(6), _fresh(topic)
        if answer is not None:
            msg = "a new lesson takes no answer"
            raise RequestError(msg, code="bad_request")
    else:
        lesson_id, state = given, _load(given, topic)
        if answer is None:
            view = await _view(lesson_id, state, {})
            return {**view, "thread": state["thread"]}
    outage.ensure_available(ctx.now())
    state, shown = copy.deepcopy(state), {}
    if answer is not None and state["pending"] is None:
        msg = "this lesson is finished"
        raise RequestError(msg, code="bad_request")
    turn = await _ask(state, answer)
    if answer is not None:
        shown = _grade(state, turn, answer)
    if shown.get("advanced"):
        state["index"], state["phase"], state["checks_left"] = (
            state["index"] + 1,
            "teach",
            0,
        )
        if state["index"] >= len(PLAN[topic]):
            turn = {}
        else:
            turn = await _ask({**state, "pending": None, "history": []}, None)
    state["pending"] = _pending(turn) if turn else None
    state["turn"] += 1
    _extend_thread(state, answer, shown)
    _save(lesson_id, state)
    if answer is not None:
        heartbeat()
    return await _view(lesson_id, state, shown)
