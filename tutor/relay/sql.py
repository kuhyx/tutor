# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Model-free chat handlers for SQL practice (``DOCS-contract-sql.md``)."""

from __future__ import annotations

import asyncio
import dataclasses
import importlib
import importlib.util
import logging
from typing import TYPE_CHECKING, Any, Final

from tutor import focus_hook
from tutor.relay.context import activity_ts
from tutor.relay.errors import RequestError
from tutor.relay.sql_protocol import TOPICS

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType

    from tutor.relay.context import RequestContext

type Json = Any
_logger = logging.getLogger(__name__)
MAX_LIST: Final = 200
MAX_DIFF: Final = 500
ENGINE_DOWN: Final = (RuntimeError, OSError, TimeoutError)


def load_sd() -> ModuleType:
    """The ``sql_drills`` package, or ``worker_error`` when it is missing."""
    if importlib.util.find_spec("sql_drills") is None:
        msg = "sql_drills is not installed on the worker"
        raise RequestError(msg, code="worker_error")
    return importlib.import_module("sql_drills")


def _plain(obj: object) -> Json:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        obj = {f.name: getattr(obj, f.name) for f in dataclasses.fields(obj)}
    if isinstance(obj, dict):
        return {str(k): _plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_plain(v) for v in obj]
    return obj


def _cut(data: dict[str, Json]) -> None:
    for key, value in list(data.items()):
        limit = MAX_DIFF if key == "cell_diff" else MAX_LIST
        if isinstance(value, list) and len(value) > limit:
            data[key] = value[:limit]
            data["truncated"] = True


def wire(raw: object) -> Json:
    """The engine's answer as JSON values, long lists cut (``truncated``)."""
    data = _plain(raw)
    if isinstance(data, dict):
        diff = data.get("cell_diff")
        if isinstance(diff, list):
            data["cell_diff"] = [["" if c is None else c for c in e] for e in diff]
        _cut(data)
        tables = data.get("tables")
        for table in tables.values() if isinstance(tables, dict) else ():
            _cut(table)
    return data


def _engine_error(exc: BaseException, drill_id: str | None) -> RequestError:
    if isinstance(exc, KeyError) and drill_id is not None:
        return RequestError(f"unknown drill {drill_id!r}", code="bad_request")
    return RequestError(f"SQL engine failed: {exc}", code="worker_error", retry=True)


async def engine_call(
    pick: Callable[[ModuleType], Callable[[], Json]],
    drill_id: str | None = None,
    *,
    ensure: bool = True,
) -> Json:
    """``pick(sd)()`` in a thread, the container started first (idempotent)."""
    sd = load_sd()

    def work() -> Json:
        if ensure:
            sd.ensure_running()
        return pick(sd)()

    try:
        return await asyncio.to_thread(work)
    except (KeyError, *ENGINE_DOWN) as exc:
        raise _engine_error(exc, drill_id) from exc


def heartbeat(ts: float | None) -> None:
    """Count one attempt as focus work; never fails the request."""
    try:
        fp = focus_hook.load_fp()
        if fp is not None:
            fp.record_activity("sql_drills", "heartbeat", ts=ts)
    except focus_hook.BROKEN:
        _logger.exception("sql heartbeat skipped")


async def sql_list(ctx: RequestContext) -> Json:
    """Every drill's meta and the topic names (no container needed)."""
    del ctx
    drills = await engine_call(lambda sd: sd.list_drills, ensure=False)
    return {"drills": wire(drills), "topics": list(TOPICS)}


async def sql_get(ctx: RequestContext) -> Json:
    """One drill's task, tables and preview; never its reference SQL."""
    drill_id = ctx.body["id"]
    return wire(await engine_call(lambda sd: lambda: sd.get_drill(drill_id), drill_id))


async def sql_run(ctx: RequestContext) -> Json:
    """Run the user's SQL on the drill's database and diff it."""
    drill_id, text = ctx.body["id"], ctx.body["sql"]
    got = await engine_call(lambda sd: lambda: sd.run(drill_id, text), drill_id)
    heartbeat(activity_ts(ctx))
    return wire(got)


async def sql_predict(ctx: RequestContext) -> Json:
    """Check a typed prediction grid against the query's real output."""
    drill_id, grid = ctx.body["id"], ctx.body["grid"]
    got = await engine_call(
        lambda sd: lambda: sd.check_prediction(drill_id, grid), drill_id
    )
    heartbeat(activity_ts(ctx))
    return wire(got)
