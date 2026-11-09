# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Model-free chat handlers for focus projects (``DOCS-contract-focus.md``).

The rules live in ``focus_project`` (imported lazily through
``tutor.focus_hook.load_fp``, so the worker also starts without it); these
handlers only translate the wire to its contract API and its errors to
``RequestError``.
"""

from __future__ import annotations

from datetime import date
import re
from typing import TYPE_CHECKING, Any, Final
import unicodedata

import earned_time

from tutor import credit, focus_hook
from tutor.relay.errors import RequestError
from tutor.relay.focus_protocol import GATES

if TYPE_CHECKING:
    from tutor.focus_hook import FocusApi, ProjectLike
    from tutor.relay.context import RequestContext

MAX_EVENT_AGE_MS: Final = 48 * 3_600_000  # a phone offline in transit delivers late
_STATUS_KEYS: Final = ("name", "minutes", "daily_minutes", "unlock_minutes", "ends")


def _fp() -> FocusApi:
    found = focus_hook.load_fp()
    if found is None:
        msg = "focus_project is not installed on the worker"
        raise RequestError(msg, code="worker_error")
    return found


def _today(ctx: RequestContext) -> date:
    return date.fromisoformat(credit.local_day(ctx.now())[0])


def _unreadable(exc: Exception) -> RequestError:
    return RequestError(
        f"focus registry unreadable: {exc}", code="worker_error", retry=True
    )


def _project(project: ProjectLike, today: date) -> dict[str, Any]:
    """The wire shape; ``end`` is the last active day (an early end shortens it)."""
    last: date = project.last_day
    left = (last - max(today, project.start)).days + 1
    return {
        "id": project.id,
        "name": project.name,
        "start": project.start.isoformat(),
        "end": last.isoformat(),
        "days_left": max(0, left),
        "replaces": list(project.replaces),
        "daily_minutes": project.daily_minutes,
        "unlock_minutes": project.unlock_minutes,
        "subjects": list(project.subjects),
        "site_patterns": list(project.site_patterns),
        "work_url": project.work_url,
    }


def _gates(today: date) -> list[dict[str, Any]]:
    return [
        {"id": e.name, "label": e.label, "replaceable": e.name in GATES}
        for e in earned_time.earners_for(today)
    ]


def _subjects(ctx: RequestContext) -> list[dict[str, str]]:
    store = ctx.engine.ctx.subjects
    out: list[dict[str, str]] = []
    for subject in store.subjects():
        meta = store.meta(subject)
        out.append({"id": subject, "title": meta.title if meta else subject})
    return out


async def focus_status(ctx: RequestContext) -> dict[str, Any]:
    """Today's project and minutes, every project, the gates and the subjects."""
    fp, today = _fp(), _today(ctx)
    try:
        active = fp.active(today)
        shown = None
        if active is not None:
            # The real minutes (121/120), not the capped pay figure; the bank
            # is what overtime leaves for tomorrow (``focus_project.carry``).
            status = fp.status(today)
            shown = _project(active, today) | {
                "minutes": status["minutes"],
                "carry_out": status.get("carry_out", 0),
            }
        listed = sorted(
            fp.list_projects(), key=lambda p: (p.created_ms, p.start), reverse=True
        )
    except (OSError, ValueError) as exc:
        raise _unreadable(exc) from exc
    return {
        "day": today.isoformat(),
        "active": shown,
        "projects": [_project(p, today) for p in listed],
        "gates": _gates(today),
        "subjects": _subjects(ctx),
    }


def _check_card(ctx: RequestContext, fp: FocusApi, today: date) -> None:
    """A ``card`` names a card of a subject of today's project, or ``bad_request``."""
    body = ctx.body
    subject, card = body["subject"], body["card"]
    if subject is None or card is None:
        msg = "focus_event: a card event needs subject and card"
        raise RequestError(msg, code="bad_request")
    try:
        active = fp.active(today)
    except (OSError, ValueError) as exc:
        raise _unreadable(exc) from exc
    if active is None or subject not in active.subjects:
        msg = f"focus_event: {subject!r} is not a subject of today's project"
        raise RequestError(msg, code="bad_request")
    if card not in ctx.engine.ctx.subjects.cards(subject):
        msg = f"focus_event: unknown card {subject}/{card}"
        raise RequestError(msg, code="bad_request")


async def focus_event(ctx: RequestContext) -> dict[str, Any]:
    """One timer tap, kept at the client's time; today's figures come back.

    ``card`` (a graded check-in card) is a ``tutor`` heartbeat at the answer
    time: focus_project 0.8.0 chains it into the open timer segment.
    """
    fp, today = _fp(), _today(ctx)
    body, created = ctx.body, ctx.request.created_ms
    if body["ts"] < created - MAX_EVENT_AGE_MS:
        msg = "focus_event: ts is more than 48 h old"
        raise RequestError(msg, code="bad_request")
    ts = min(body["ts"], created) / 1000  # a client clock ahead is clamped
    card = body["event"] == "card"
    if card:
        _check_card(ctx, fp, today)
    source, kind = ("tutor", "heartbeat") if card else ("timer", body["event"])
    try:
        fp.record_activity(source, kind, ts=ts, dev=body["platform"])
        status = fp.status(today)
    except (OSError, ValueError) as exc:
        raise _unreadable(exc) from exc
    return (
        {k: status[k] for k in _STATUS_KEYS}
        | {"replaces": list(status["replaces"])}
        | {"carry_out": status.get("carry_out", 0)}
    )


def _slug_of(name: str) -> str:
    """An ascii lowercase slug of ``name`` (``project`` if nothing is left)."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")[:40].strip("-")
    return slug or "project"


def _free_id(name: str, taken: set[str]) -> str:
    base = _slug_of(name)
    found, n = base, 1
    while found in taken:
        n += 1
        found = f"{base}-{n}"
    return found


async def focus_create(ctx: RequestContext) -> dict[str, Any]:
    """Create a project; a refusal (overlap, bad dates) is ``focus_refused``."""
    fp, body = _fp(), ctx.body
    try:
        taken = {p.id for p in fp.list_projects()}
        made = fp.create_project(
            _free_id(body["name"], taken),
            name=body["name"],
            start=date.fromisoformat(body["start"]),
            end=date.fromisoformat(body["end"]),
            replaces=body["replaces"],
            daily_minutes=body["daily_minutes"],
            unlock_minutes=body["unlock_minutes"],
            subjects=body["subjects"],
            site_patterns=body["site_patterns"],
            work_url=body["work_url"] or "",
        )
    except ValueError as exc:
        raise RequestError(str(exc), code="focus_refused") from exc
    return {"id": made.id}


async def focus_update(ctx: RequestContext) -> dict[str, Any]:
    """Edit a project (every field, like create); a refusal is ``focus_refused``."""
    fp, body, today = _fp(), ctx.body, _today(ctx)
    # An older client never sends work_url: absent keeps it, "" clears it.
    kept = {} if body["work_url"] is None else {"work_url": body["work_url"]}
    try:
        done = fp.apply_update(
            body["id"],
            today=today,
            **kept,
            name=body["name"],
            start=date.fromisoformat(body["start"]),
            end=date.fromisoformat(body["end"]),
            replaces=body["replaces"],
            daily_minutes=body["daily_minutes"],
            unlock_minutes=body["unlock_minutes"],
            subjects=body["subjects"],
            site_patterns=body["site_patterns"],
        )
    except KeyError as exc:
        msg = f"unknown project {body['id']!r}"
        raise RequestError(msg, code="focus_refused") from exc
    except ValueError as exc:
        raise RequestError(str(exc), code="focus_refused") from exc
    except OSError as exc:
        raise _unreadable(exc) from exc
    first = done.effective_from
    out: dict[str, Any] = {"id": body["id"], "effective_from": first.isoformat()}
    if first > today:
        out["message"] = (
            f"Saved. Lower targets and newly replaced gates apply from {first}; "
            "today keeps the old ones."
        )
    return out


async def focus_end(ctx: RequestContext) -> dict[str, Any]:
    """End a project early: ``day`` (default today) is its last active day.

    A past ``day`` is refused: it would erase that day's shortfall and lift
    the focus lock. The app sends no ``day`` (= today).
    """
    fp, body, today = _fp(), ctx.body, _today(ctx)
    day = date.fromisoformat(body["day"]) if body["day"] else today
    if day < today:
        msg = f"cannot end {body['id']!r} in the past ({day})"
        raise RequestError(msg, code="focus_refused")
    try:
        fp.end_project(body["id"], day)
    except KeyError as exc:
        msg = f"unknown project {body['id']!r}"
        raise RequestError(msg, code="focus_refused") from exc
    except ValueError as exc:
        raise RequestError(str(exc), code="focus_refused") from exc
    return {}
