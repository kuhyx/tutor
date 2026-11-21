#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Agent-E2E helpers of the Focus flows (F7, F8 in ``e2e_focus``; F9-F11).

The sandbox's ``activity.jsonl`` rows, waiting for its timer events, and a
project covering today created through the relay (``focus_create``).
``e2e_focus`` imports every name, so ``from e2e_focus import _activity``
(``e2e_checkin``, ``e2e_unbacked``) keeps working.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import json
import time
from typing import TYPE_CHECKING, Any
import uuid

from e2e_flow import FlowError

from tutor.curriculum.ids import ulid

if TYPE_CHECKING:
    from pathlib import Path

    from e2e_flow import Flow


def _activity(path: Path) -> list[dict[str, Any]]:
    """The sandbox's ``activity.jsonl`` rows, oldest first."""
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _wait_events(flow: Flow, path: Path, want: list[str], timeout: float = 20) -> None:
    """Block until the file's timer events are exactly ``want``."""
    flow.step(f"activity.jsonl timer events == {want}")
    deadline = time.monotonic() + timeout
    seen: list[str] = []
    while time.monotonic() < deadline:
        seen = [r["kind"] for r in _activity(path) if r["source"] == "timer"]
        if seen == want:
            flow.note(f"{path}: {seen}")
            return
        time.sleep(0.5)
    msg = f"timer events {seen}, want {want} in {path}"
    raise FlowError(msg)


def _create_project(flow: Flow, subjects: list[str] | None = None) -> None:
    """Send ``focus_create`` for a project covering today and wait for ok."""
    flow.step(f"focus_create: a project covering today, subjects {subjects or []}")
    now = int(time.time() * 1000)
    rid = ulid(now)
    today = datetime.now().astimezone().date()  # the worker's local day
    flow.db.put(
        f"requests/{rid}/req",
        {
            "kind": "focus_create",
            "dev": str(uuid.uuid4()),
            "created": now,
            "body": {
                "name": "E2E focus",
                "start": today.isoformat(),
                "end": (today + timedelta(days=2)).isoformat(),
                "replaces": ["leetcode"],
                "daily_minutes": 60,
                "unlock_minutes": 10,
                "subjects": subjects or [],
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
