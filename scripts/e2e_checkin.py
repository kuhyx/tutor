#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Agent-E2E flows F9, F10: the focus check-in card (``DOCS-contract-focus.md``).

Same sandbox and page hooks as F7 (``e2e_focus.py``). The worker clamps a
``ts`` ahead of its clock, so these flows move the app clock BACK first and
then forward through the check-in: every ``ts`` stays in the past and lands
in ``activity.jsonl`` unchanged. One call each, under 60 s, after ``up``.

F9: a project whose subject has taught cards; Start; at 421 s the card (not
the "Still working" tap); rated after >= 1 s -> ``timer/start`` then
``tutor/heartbeat`` at the review's own ``at``, no ``checkin``; the review
carries ``src: checkin`` in the RTDB log and in the worker's log; Stop at
701 s -> focus_project (0.8.0) counts >= 11 minutes (0.7.1: 5).
F10: the same, but rated at 650 s, past the lapse: "Missed a check-in" and
the card; the rating is graded and sends ``start``: the file has ``start,
start`` and no heartbeat.
"""

from __future__ import annotations

from datetime import datetime
import os
import time
from typing import TYPE_CHECKING, Any

from e2e_flow import FlowError
from e2e_focus import (
    PAGE_HOOK,
    ROUTE,
    START,
    STOP,
    _activity,
    _create_project,
    _wait_events,
)
import focus_project as fp

from tutor.curriculum.context import Context

if TYPE_CHECKING:
    from pathlib import Path

    from e2e_flow import Flow

REVEAL, MISSED, TAP = "Show answer (Space)", "Missed a check-in", "Still working"
# Start to Stop is 701 s: one chained segment counts 11 minutes (0.7.1: 5).
CHAINED_MINUTES = 11


def _clock(flow: Flow, seconds: int) -> int:
    """Move the app clock by ``seconds``; the app's now (ms) after it."""
    flow.step(f"move the app clock {seconds:+d} s")
    flow.browser.evaluate(f"window.__skew({seconds * 1000})")
    now = flow.browser.evaluate("Date.now()")
    if not isinstance(now, int | float):
        msg = f"Date.now() returned {now!r}"
        raise FlowError(msg)
    return int(now)


def _start(flow: Flow, subject: str, back_s: int) -> Path:
    """A project on ``subject``, the Focus screen, Start at now - ``back_s``."""
    activity: Path = flow.args.focus / "activity.jsonl"
    flow.step(f"precondition: {activity} has no timer events")
    if any(r["source"] == "timer" for r in _activity(activity)):
        msg = "sandbox focus data is not fresh (run e2e_sandbox.sh up)"
        raise FlowError(msg)
    _create_project(flow, subjects=[subject])
    flow.step("install the page hooks (Notification, timers, clock)")
    flow.browser.call("Page.enable")
    flow.browser.call("Page.addScriptToEvaluateOnNewDocument", source=PAGE_HOOK)
    flow.screen(ROUTE)
    flow.expect("E2E focus", START)
    _clock(flow, -back_s)
    flow.tap(START)
    _wait_events(flow, activity, ["start"])
    return activity


def _card_shown(flow: Flow, *also: str) -> None:
    """The check-in card is on screen (its Show answer), not the old tap."""
    flow.expect(REVEAL, *also, timeout=20)
    flow.step("the old Still working tap is not offered")
    if flow.browser.find(TAP) is not None:
        msg = "the Still working tap shows next to the card"
        raise FlowError(msg)


def _rate(flow: Flow, label: str) -> None:
    flow.step("wait 1.5 s (the 1 s presence floor)")
    time.sleep(1.5)
    flow.tap(REVEAL)
    flow.tap(label)


def _review(flow: Flow, subject: str) -> dict[str, Any]:
    """The app's check-in review in the RTDB log (``src: checkin``)."""
    flow.step("the RTDB log has the review with src checkin")
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        found = [
            e
            for events in flow.db.node("log").values()
            if isinstance(events, dict)
            for e in events.values()
            if isinstance(e, dict)
            and e.get("k") == "review"
            and e.get("src") == "checkin"
            and e.get("s") == subject
        ]
        if found:
            flow.note(f"review: {found[-1]}")
            return found[-1]
        time.sleep(0.5)
    msg = "no review with src checkin in the RTDB log"
    raise FlowError(msg)


def _worker_has(flow: Flow, review: dict[str, Any]) -> None:
    """The worker's own log kept the review and its ``src`` (eventlog)."""
    flow.step("the worker's log has the review, src kept")
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        for e in Context(flow.args.data, device="e2e-reader").log.read():
            if e.get("at") == review["at"] and e.get("k") == "review":
                if e.get("src") != "checkin":
                    msg = f"worker dropped src: {e}"
                    raise FlowError(msg)
                flow.note(f"worker: {e}")
                return
        time.sleep(0.5)
    msg = f"the worker never logged the review at {review['at']}"
    raise FlowError(msg)


def _beats(path: Path) -> list[dict[str, Any]]:
    return [r for r in _activity(path) if r["source"] == "tutor"]


def _minutes(flow: Flow) -> int:
    """Today's real minutes by the sandbox's focus_project (0.8.0)."""
    os.environ["FOCUS_PROJECT_DATA"] = str(flow.args.focus)  # read per call
    status = fp.status(datetime.now().astimezone().date())
    return int(status["minutes"])


def f9(flow: Flow) -> None:
    """Card at 421 s, rated: a tutor heartbeat backs the timer past 600 s."""
    subject = flow.args.subject
    activity = _start(flow, subject, back_s=720)
    _clock(flow, 421)
    _card_shown(flow)
    flow.shot("card")
    _rate(flow, "3 Good")
    review = _review(flow, subject)
    flow.step("activity: start, then one tutor heartbeat at the review's at")
    deadline = time.monotonic() + 15
    while not _beats(activity) and time.monotonic() < deadline:
        time.sleep(0.5)
    beats = _beats(activity)
    if len(beats) != 1 or beats[0]["kind"] != "heartbeat":
        msg = f"tutor events {beats}"
        raise FlowError(msg)
    if round(beats[0]["ts"] * 1000) != review["at"]:
        msg = f"heartbeat ts {beats[0]['ts']} != review at {review['at']}"
        raise FlowError(msg)
    flow.note(f"heartbeat {beats[0]}")
    _wait_events(flow, activity, ["start"], timeout=2)
    _worker_has(flow, review)
    _clock(flow, 280)
    flow.tap(STOP)
    _wait_events(flow, activity, ["start", "stop"])
    flow.step("the segment survives past 600 s: >= 11 minutes (0.7.1: 5)")
    got = _minutes(flow)
    flow.note(f"minutes={got}")
    if got < CHAINED_MINUTES:
        msg = f"minutes {got}: the heartbeat did not chain the segment"
        raise FlowError(msg)
    flow.shot("stopped")


def f10(flow: Flow) -> None:
    """Rated at 650 s, after the lapse: graded, and a new segment starts."""
    subject = flow.args.subject
    activity = _start(flow, subject, back_s=700)
    _clock(flow, 650)
    _card_shown(flow, MISSED)
    flow.shot("lapsed")
    _rate(flow, "1 Again")
    _review(flow, subject)
    _wait_events(flow, activity, ["start", "start"])
    if beats := _beats(activity):
        msg = f"a late rating wrote a heartbeat: {beats}"
        raise FlowError(msg)
    flow.tap(STOP)
    _wait_events(flow, activity, ["start", "start", "stop"])
    flow.shot("stopped")
