# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Interview projects over the relay (``DOCS-contract-focus.md``, Interview).

``focus_project`` owns every rule: milestones are generated from the project,
trips and weekend answers only ratchet stricter, evidence is append-only.
This module translates the wire to that API; whatever it refuses comes back
as a ``focus_refused`` result carrying its own text, never swallowed.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
import tempfile
from typing import TYPE_CHECKING, Any, Final, NoReturn, cast

from tutor.relay import focus_upload
from tutor.relay.errors import RequestError
from tutor.relay.focus_common import load_api, local_now, registry
from tutor.store import data_dir

if TYPE_CHECKING:
    from tutor.focus_hook import FocusApi, ProjectLike
    from tutor.relay.context import RequestContext

INTERVIEW: Final = "interview"
SATURDAY: Final = 5


def _is_interview(project: ProjectLike) -> bool:
    return getattr(project, "kind", "focus") == INTERVIEW


def _bad(why: str) -> NoReturn:
    msg = f"focus_create: {why}"
    raise RequestError(msg, code="bad_request")


def saturdays(first: date, test_day: date) -> list[date]:
    """The Saturdays from ``first`` up to the day before the test."""
    day = first + timedelta(days=(SATURDAY - first.weekday()) % 7)
    found: list[date] = []
    while day < test_day:
        found.append(day)
        day += timedelta(days=7)
    return found


def _block(project: ProjectLike) -> dict[str, Any]:
    return {
        "trips": [
            {"start": t.start.isoformat(), "end": t.end.isoformat()}
            for t in project.trips
        ],
        "weekend_answers": {d.isoformat(): a for d, a in project.weekend_answers},
    }


def project_fields(project: ProjectLike) -> dict[str, Any]:
    """The interview part of a project row (just ``kind`` for a focus project)."""
    if not _is_interview(project):
        return {"kind": "focus"}
    return {
        "kind": INTERVIEW,
        "test_at": project.test_at.isoformat() if project.test_at else None,
        "invite_url": project.invite_url,
        **_block(project),
    }


def _rows(fp: FocusApi, project: ProjectLike, now: datetime) -> dict[str, Any]:
    found = fp.milestones(project, now)
    return {
        "milestones": [m.to_dict() for m in found],
        "missed": any(m.red for m in found),
    }


def active_fields(
    fp: FocusApi, project: ProjectLike, status: dict[str, Any], now: datetime
) -> dict[str, Any]:
    """Milestones and ``missed`` of the active project; the day's real targets."""
    if not _is_interview(project):
        return {"milestones": [], "missed": False}
    return {
        **_rows(fp, project, now),
        "daily_minutes": status["daily_minutes"],
        "unlock_minutes": status["unlock_minutes"],
    }


def create_fields(fp: FocusApi, body: dict[str, Any]) -> dict[str, Any]:
    """``create_project`` kwargs for the interview fields; ``bad_request`` if off."""
    if body["kind"] != INTERVIEW:
        if body["test_at"] or body["invite_url"] or body["trips"] or body["no_trip"]:
            _bad("test_at, invite_url, trips and no_trip need kind interview")
        return {}
    if body["test_at"] is None:
        _bad("an interview needs test_at")
    if bool(body["trips"]) == body["no_trip"]:
        _bad("send trips, or no_trip true for none (exactly one)")
    ranges = [
        (date.fromisoformat(t["start"]), date.fromisoformat(t["end"]))
        for t in body["trips"]
    ]
    test_at = datetime.fromisoformat(body["test_at"])
    # A weekend an announced trip covers is a trip: answer it, or the unanswered
    # question would read as missed on its Thursday.
    start = date.fromisoformat(body["start"])
    answers = {
        sat: True
        for sat in saturdays(start, test_at.date())
        if any(first <= sat <= last for first, last in ranges)
    }
    return {
        "kind": INTERVIEW,
        "test_at": test_at,
        "invite_url": body["invite_url"],
        "trips": [fp.Trip(first, last) for first, last in ranges],
        "weekend_answers": answers,
    }


def _after(fp: FocusApi, project_id: str, now: datetime) -> dict[str, Any]:
    """What the client needs after a change: milestones, trips and answers."""
    project = {p.id: p for p in fp.list_projects()}[project_id]
    return {**_rows(fp, project, now), **_block(project)}


def _record_file(
    fp: FocusApi, pid: str, milestone: str, upload: tuple[bytes, str], now: datetime
) -> None:
    """Hand the registry a real file; it copies it, the scratch copy is dropped."""
    image, suffix = upload
    scratch = data_dir() / "tmp"
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as folder:
        path = Path(folder) / f"screenshot{suffix}"
        path.write_bytes(image)
        fp.record_evidence(pid, milestone, "file", file=path, now=now)


async def focus_evidence(ctx: RequestContext) -> dict[str, Any]:
    """Record one piece of evidence; the registry decides what fits which milestone."""
    fp, body, now = load_api(), ctx.body, local_now(ctx)
    pid, milestone, kind = body["id"], body["milestone"], body["kind"]
    if kind == "file":
        upload = await focus_upload.fetch(ctx.rtdb, body)
        with registry():
            _record_file(fp, pid, milestone, upload, now)
    else:
        with registry():
            fp.record_evidence(pid, milestone, kind, body["value"], now=now)
    with registry():
        return _after(fp, pid, now)


async def focus_trip(ctx: RequestContext) -> dict[str, Any]:
    """Announce a trip (it may only grow) and answer the weekends it covers."""
    fp, body, now = load_api(), ctx.body, local_now(ctx)
    pid = body["id"]
    first, last = date.fromisoformat(body["start"]), date.fromisoformat(body["end"])
    with registry():
        fp.add_trip(pid, first, last, now=now)
        project = {p.id: p for p in fp.list_projects()}[pid]
        answers = dict(project.weekend_answers)
        test_day = cast("datetime", project.test_at).date()
        for sat in saturdays(project.start, test_day):
            if first <= sat <= last and answers.get(sat) is not True:
                fp.answer_weekend(pid, sat, trip=True, now=now)
        return _after(fp, pid, now)


async def focus_weekend(ctx: RequestContext) -> dict[str, Any]:
    """Answer the trip question of one weekend (a True never flips back)."""
    fp, body, now = load_api(), ctx.body, local_now(ctx)
    with registry():
        saturday = date.fromisoformat(body["saturday"])
        fp.answer_weekend(body["id"], saturday, trip=body["trip"], now=now)
        return _after(fp, body["id"], now)
