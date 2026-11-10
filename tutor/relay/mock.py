# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The ``mock`` kind: a timed mock test (Python MCQs, a palindrome task, SQL).

``start`` assembles the paper and stores the keys here, on the server; the
phone only ever sees public task fields. ``answer`` records one task's
submission (queued offline on the phone, replayed with the tap time),
``run`` shows output with no verdict, ``finish`` grades everything, ``get``
resumes. Every answer or run counts as focus work.
"""

from __future__ import annotations

import asyncio
import secrets
from typing import TYPE_CHECKING, Any, Final, NamedTuple

from tutor.relay import (
    mock_grade,
    mock_mcq,
    mock_palin,
    mock_pool,
    mock_sql,
    mock_store,
)
from tutor.relay.context import activity_ts
from tutor.relay.errors import RequestError
from tutor.relay.sql import engine_call, heartbeat, wire

if TYPE_CHECKING:
    import random

    from tutor.relay.context import RequestContext

type Json = Any
GRACE_MS: Final = 90_000


def _bad(why: str) -> RequestError:
    return RequestError(why, code="bad_request")


def _need(body: dict[str, Any], *names: str) -> None:
    for name in names:
        if not body.get(name):
            msg = f"mock: {name!r} is required"
            raise _bad(msg)


def _mcq_tasks(
    questions: list[Json], rnd: random.Random
) -> tuple[list[Json], list[Json]]:
    public: list[Json] = []
    private: list[Json] = []
    for n, q in enumerate(questions, start=1):
        options = [q["correct"], *q["wrong"]]
        rnd.shuffle(options)
        task = f"mq{n}"
        public.append(
            {
                "id": task,
                "section": "py_mcq",
                "title": f"Python {n}",
                "topic": q["topic"],
                "prompt_md": "What does this print?",
                "code": q["code"],
                "options": options,
            }
        )
        private.append({"id": task, "key": options.index(q["correct"])})
    return public, private


class Parts(NamedTuple):
    """What a paper is built from: MCQs, SQL tasks, the palindrome task, notes."""

    questions: list[Json]
    sql: tuple[list[Json], list[Json], list[str]]
    palin: mock_palin.PalinTask
    notes: list[str]


def compose(rnd: random.Random, now: float, minutes: int, parts: Parts) -> Json:
    """The stored paper (public tasks, private keys) for ``parts``."""
    sql_pub, sql_priv, sql_notes = parts.sql
    mcq_pub, mcq_priv = _mcq_tasks(parts.questions, rnd)
    started = int(now * 1000)
    return {
        "id": secrets.token_hex(6),
        "started_ms": started,
        "deadline_ms": started + minutes * 60_000,
        "minutes": minutes,
        "tasks": [*mcq_pub, mock_palin.public(parts.palin), *sql_pub],
        "private": [*mcq_priv, {"id": "pc1", "palin": parts.palin.key}, *sql_priv],
        "answers": {},
        "notes": [*parts.notes, *sql_notes],
    }


def _activate(mock: Json, now: float, minutes: int) -> Json:
    """Start the clock on a pre-built paper."""
    started = int(now * 1000)
    mock |= {
        "started_ms": started,
        "deadline_ms": started + minutes * 60_000,
        "minutes": minutes,
    }
    return mock


async def start(ctx: RequestContext) -> Json:
    """A pre-built paper if one waits, else assemble one (model calls overlap)."""
    now = ctx.now()
    minutes = ctx.body["minutes"]
    ready = await asyncio.to_thread(mock_pool.take)
    if ready is not None:
        mock = _activate(ready, now, minutes)
        mock_store.save(mock)
        return _public(mock)
    rnd = secrets.SystemRandom()
    (questions, notes), sql = await asyncio.gather(
        mock_mcq.assemble(rnd, now),
        mock_sql.pick(rnd, mock_store.seen_drills()),
    )
    parts = Parts(questions, sql, mock_palin.pick(rnd), notes)
    mock = compose(rnd, now, minutes, parts)
    mock_store.save(mock)
    return _public(mock)


def _public(mock: dict[str, Json]) -> Json:
    keys = ("started_ms", "deadline_ms", "minutes", "tasks", "notes")
    out = {"mock_id": mock["id"], **{k: mock[k] for k in keys}}
    out["answers"] = {t: a["text"] for t, a in mock["answers"].items()}
    if mock.get("result"):
        out["result"] = mock["result"]
    return out


def _task(mock: dict[str, Json], task: str | None) -> tuple[Json, Json]:
    if task is None:
        msg = "mock: 'task' is required"
        raise _bad(msg)
    for pub, priv in zip(mock["tasks"], mock["private"], strict=True):
        if pub["id"] == task:
            return pub, priv
    msg = f"mock: unknown task {task!r}"
    raise _bad(msg)


async def answer(ctx: RequestContext) -> Json:
    """Store one task's submission; one past the deadline is ignored (late)."""
    body = ctx.body
    _need(body, "mock_id")
    mock = mock_store.load(body["mock_id"])
    _task(mock, body["task"])
    ts = body["ts"] or int(ctx.now() * 1000)
    late = bool(mock.get("result")) or ts > mock["deadline_ms"] + GRACE_MS
    if not late:
        mock["answers"][body["task"]] = {"text": body["answer"], "ts": ts}
        mock_store.save(mock)
    heartbeat(activity_ts(ctx))
    return {"ok": True, "late": late}


async def run(ctx: RequestContext) -> Json:
    """Run an answer for output only (no verdict, no expected rows)."""
    body = ctx.body
    _need(body, "mock_id", "answer")
    mock = mock_store.load(body["mock_id"])
    pub, priv = _task(mock, body["task"])
    heartbeat(activity_ts(ctx))
    if pub["section"] == "sql":
        got = wire(
            await engine_call(
                lambda sd: lambda: sd.run(priv["drill"], body["answer"]), priv["drill"]
            )
        )
        return {k: got.get(k) for k in ("ok", "error", "columns", "rows")}
    if pub["section"] == "py_code":
        task = mock_grade.palin(priv)
        results = await asyncio.to_thread(
            mock_palin.run, task, body["answer"], hidden=False
        )
        return {"ok": all(r["ok"] for r in results), "examples": results}
    msg = "mock: only code and SQL tasks can be run"
    raise _bad(msg)


async def finish(ctx: RequestContext) -> Json:
    """Grade every task once; a second call returns the stored result."""
    _need(ctx.body, "mock_id")
    mock = mock_store.load(ctx.body["mock_id"])
    if mock.get("result"):
        return mock["result"]
    given = {t: a["text"] for t, a in mock["answers"].items()}
    items = [
        await mock_grade.grade(pub, priv, given.get(pub["id"], ""))
        for pub, priv in zip(mock["tasks"], mock["private"], strict=True)
    ]
    score = sum(1 for i in items if i["correct"])
    result = {
        "mock_id": mock["id"],
        "score": score,
        "total": len(items),
        "percent": round(100 * score / len(items)),
        "finished_ms": int(ctx.now() * 1000),
        "tasks": items,
    }
    mock["result"] = result
    mock_store.save(mock)
    return result


async def get(ctx: RequestContext) -> Json:
    """The paper, the answers so far and the result when finished."""
    _need(ctx.body, "mock_id")
    return _public(mock_store.load(ctx.body["mock_id"]))


OPS: Final = {
    "start": start,
    "answer": answer,
    "run": run,
    "finish": finish,
    "get": get,
}


async def mock_request(ctx: RequestContext) -> Json:
    """Dispatch on ``body['op']``."""
    return await OPS[ctx.body["op"]](ctx)
