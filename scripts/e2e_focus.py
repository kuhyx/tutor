#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Agent-E2E flow F7: the desktop Focus project screen (``DOCS-contract-focus.md``).

Runs on a sandbox that is ``up`` (``e2e_sandbox.sh``): the worker's
``FOCUS_PROJECT_DATA`` is ``<sandbox>/focus`` (``--focus``), never the live
``~/.local/share/focus_project``. Model-free; one call, under 60 s.

1. a project covering today is created through the relay (``focus_create``,
   as the form would send it) and shows on the Focus screen;
2. the page hooks are installed (see ``PAGE_HOOK``): a recording
   ``Notification`` (permission granted) and the 9-minute check-in timer
   shortened, so the run needs seconds, not minutes;
3. Start -> the worker records ``timer/start`` in ``activity.jsonl``;
4. the check-in is due: the browser notification fires (``Still working?``)
   and clicking it records ``timer/checkin``; so does the screen's own
   "Still working" button;
5. Stop -> ``timer/stop``. The file must hold start, checkin, checkin, stop
   in order, each ``dev == "pc"``; the screen shows the day's minutes.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import json
from pathlib import Path
import time
from typing import Any
import uuid

from e2e_flow import Flow, FlowError

from tutor.curriculum.ids import ulid

ROUTE = "/focus"
START, CHECKIN, STOP = "Start", "Still working", "Stop"
# Page-side, before the app boots: a Notification that is granted, recorded
# in ``window.__notes`` and clickable by the script; timers of 60 s or more
# run 100x faster (the notifier's 9 minutes become 5.4 s); ``__skew(ms)``
# moves the app clock forward, so the timer's own gap check (check-in due at
# 540 s, lapse at 600 s) is reached in seconds without a lapse.
SKEW_MS = 535_000
PAGE_HOOK = """
(() => {
  window.__notes = [];
  class N {
    static permission = 'granted';
    static requestPermission() { return Promise.resolve('granted'); }
    constructor(title, options) {
      this.title = title; this.options = options; this.closed = false;
      window.__notes.push(this);
    }
    close() { this.closed = true; }
  }
  window.Notification = N;
  for (const name of ['setTimeout', 'setInterval']) {
    const real = window[name].bind(window);
    window[name] = (fn, ms, ...rest) => real(fn, ms >= 60000 ? ms / 100 : ms, ...rest);
  }
  let skew = 0;
  const now = Date.now.bind(Date);
  Date.now = () => now() + skew;
  window.__skew = (ms) => { skew += ms; return skew; };
})();
"""


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


def _create_project(flow: Flow) -> None:
    """Send ``focus_create`` for a project covering today and wait for ok."""
    flow.step("focus_create: a project covering today")
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


def _notification_click(flow: Flow) -> None:
    """Wait for the browser notification, then click it (its ``onclick``)."""
    flow.step('a browser Notification "Still working?" fires, then is clicked')
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        shown = flow.browser.evaluate(
            "window.__notes.map(n => ({title: n.title, tag: n.options.tag}))"
        )
        if isinstance(shown, list) and shown:
            flow.note(f"notification: {shown[-1]}")
            if shown[-1]["title"] != "Still working?":
                msg = f"unexpected notification {shown[-1]}"
                raise FlowError(msg)
            clicked = flow.browser.evaluate(
                "(() => { const n = window.__notes.at(-1);"
                " if (!n.onclick) return false; n.onclick(); return n.closed; })()"
            )
            if clicked is not True:
                msg = f"notification click did not close it (got {clicked!r})"
                raise FlowError(msg)
            return
        time.sleep(0.5)
    msg = "no browser notification in 20 s (permission, or the timer never armed)"
    raise FlowError(msg)


def _skew(flow: Flow) -> None:
    """Move the app clock to just before the next check-in is due."""
    flow.step(f"move the app clock forward {SKEW_MS // 1000} s")
    flow.browser.evaluate(f"window.__skew({SKEW_MS})")


def f7(flow: Flow) -> None:
    """Focus screen: start, notification check-in, button check-in, stop."""
    activity = Path(flow.args.focus) / "activity.jsonl"
    flow.step(f"precondition: {activity} has no timer events")
    if any(r["source"] == "timer" for r in _activity(activity)):
        msg = "sandbox focus data is not fresh (run e2e_sandbox.sh up)"
        raise FlowError(msg)
    _create_project(flow)
    flow.step("install the page hooks (Notification, shortened timers)")
    flow.browser.call("Page.enable")
    flow.browser.call("Page.addScriptToEvaluateOnNewDocument", source=PAGE_HOOK)
    flow.screen(ROUTE)
    flow.expect("E2E focus", START)
    flow.shot("project")
    flow.tap(START)
    _wait_events(flow, activity, ["start"])
    _skew(flow)
    flow.expect(STOP)
    flow.shot("running")
    _notification_click(flow)
    _wait_events(flow, activity, ["start", "checkin"])
    _skew(flow)
    flow.expect(CHECKIN)
    flow.shot("prompt")
    flow.tap(CHECKIN)
    _wait_events(flow, activity, ["start", "checkin", "checkin"])
    flow.tap(STOP)
    _wait_events(flow, activity, ["start", "checkin", "checkin", "stop"])
    rows = [r for r in _activity(activity) if r["source"] == "timer"]
    if bad := [r for r in rows if r.get("dev") != "pc"]:
        msg = f"events not tagged dev=pc: {bad}"
        raise FlowError(msg)
    flow.shot("stopped")
