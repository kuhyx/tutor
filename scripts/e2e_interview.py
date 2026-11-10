#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Agent-E2E flow F15: an interview project's milestone icon row on Focus.

Same sandbox as F7 (``e2e_focus.py``): the worker's ``FOCUS_PROJECT_DATA`` is
``<sandbox>/focus``, never the live ``~/.local/share/focus_project``. Model-free;
one call, under 60 s, after a fresh ``up``.

Phases (the one-call flows ignore them otherwise): ``send`` creates the
project, ``check`` only asserts, ``all`` (default) does both. ``check`` on a
sandbox with no interview project is the red run.

1. ``focus_create`` with ``kind: interview`` (test 4 days ahead, an invite
   url, an explicit no-trip) through the relay, as the form would send it;
2. the Focus screen shows the project and every milestone icon, found by
   its spoken ``interview-ms-<slot>`` label (the icons carry no text).
"""

from __future__ import annotations

from datetime import datetime, timedelta
import json
import time
from typing import TYPE_CHECKING
import uuid

from e2e_flow import FlowError
from e2e_focus import ROUTE, START

from tutor.curriculum.ids import ulid

if TYPE_CHECKING:
    from e2e_flow import Flow

NAME = "E2E interview"
SLOTS = ("rules", "trip", "phone", "clock", "mock", "slot")
LABELS = tuple(f"interview-ms-{slot}" for slot in SLOTS)
TEST_IN_DAYS = 4


def _create_interview(flow: Flow) -> None:
    """Send an interview ``focus_create`` and wait for its ok result."""
    flow.step(f"focus_create kind=interview, test in {TEST_IN_DAYS} days, no trip")
    now = int(time.time() * 1000)
    rid = ulid(now)
    test_at = datetime.now().astimezone().replace(
        hour=10, minute=0, second=0, microsecond=0
    ) + timedelta(days=TEST_IN_DAYS)
    flow.db.put(
        f"requests/{rid}/req",
        {
            "kind": "focus_create",
            "dev": str(uuid.uuid4()),
            "created": now,
            "body": {
                "name": NAME,
                "kind": "interview",
                "start": datetime.now().astimezone().date().isoformat(),
                "end": test_at.date().isoformat(),
                "replaces": ["leetcode"],
                "daily_minutes": 30,
                "unlock_minutes": 10,
                "subjects": [],
                "test_at": test_at.strftime("%Y-%m-%dT%H:%M"),
                "invite_url": "https://example.com/test",
                "no_trip": True,
            },
        },
    )
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if result := flow.result_of(rid):
            if not result.get("ok"):
                msg = f"focus_create refused: {json.dumps(result)[:300]}"
                raise FlowError(msg)
            flow.note(f"rid={rid} result={json.dumps(result)[:200]}")
            return
        time.sleep(0.5)
    msg = "no focus_create result in 20 s"
    raise FlowError(msg)


def _check_row(flow: Flow) -> None:
    """The Focus screen shows the project and all six milestone icons."""
    flow.screen(ROUTE)
    flow.expect(NAME, START, *LABELS)
    flow.shot("row")


def f15(flow: Flow) -> None:
    """Interview project: created through the relay, its icon row is on Focus."""
    phase = str(flow.args.phase)
    if phase in {"send", "all"}:
        _create_interview(flow)
    if phase in {"check", "all"}:
        _check_row(flow)
