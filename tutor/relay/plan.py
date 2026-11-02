# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Today's linear plan: ``<data>/plan/<date>.json``, edited on disk, no APK.

The file is ``{"steps": [{id, title, what, kind, target}]}`` plus a
``"done": [ids]`` list the handlers maintain. ``plan_today`` returns the
steps with ``done`` flags and ``current`` (the first step not done). A step
the server saw done (``plan_auto``) is added to ``done`` on the way.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, Final

from tutor import credit
from tutor.relay import plan_auto
from tutor.relay.errors import RequestError
from tutor.store import data_dir

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.relay.context import RequestContext

type Json = Any
_logger = logging.getLogger(__name__)
KINDS: Final = ("coach", "sql_lesson", "sql_drill", "cards", "mock", "note")


def _path(day: str) -> Path:
    return data_dir() / "plan" / f"{day}.json"


def _read(day: str) -> dict[str, Json]:
    path = _path(day)
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError, ValueError:
        _logger.warning("plan file for %s is unreadable", day)
        return {}
    return raw if isinstance(raw, dict) else {}


def _steps(raw: dict[str, Json]) -> list[dict[str, Json]]:
    steps = raw.get("steps")
    if not isinstance(steps, list):
        return []
    ok = [s for s in steps if isinstance(s, dict) and isinstance(s.get("id"), str)]
    return [s for s in ok if s.get("kind") in KINDS]


def _write(day: str, raw: dict[str, Json]) -> None:
    target = _path(day)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(target)


def _view(ctx: RequestContext) -> Json:
    """The plan with ``done`` flags; what the server saw done is ticked for good."""
    day = credit.local_day(ctx.now())[0]
    raw = _read(day)
    steps = _steps(raw)
    done = [d for d in raw.get("done", []) if isinstance(d, str)]
    seen = plan_auto.auto_done(ctx, [s for s in steps if s["id"] not in done])
    if seen:
        done = [*done, *seen]
        try:
            _write(day, {**raw, "done": done})
        except OSError:
            _logger.warning("plan file for %s is not writable", day)
    marked = [{**s, "done": s["id"] in done} for s in steps]
    current = next((s["id"] for s in marked if not s["done"]), None)
    return {"date": day, "steps": marked, "current": current}


async def plan_today(ctx: RequestContext) -> Json:
    """Today's plan (empty ``steps`` when none was written)."""
    return _view(ctx)


async def plan_step_done(ctx: RequestContext) -> Json:
    """Mark one step of today's plan done (idempotent); returns the plan."""
    day = credit.local_day(ctx.now())[0]
    raw = _read(day)
    step_id = ctx.body["id"]
    if step_id not in {s["id"] for s in _steps(raw)}:
        msg = f"plan: unknown step {step_id!r}"
        raise RequestError(msg, code="bad_request")
    done = [d for d in raw.get("done", []) if isinstance(d, str)]
    if step_id not in done:
        _write(day, {**raw, "done": [*done, step_id]})
    return _view(ctx)
