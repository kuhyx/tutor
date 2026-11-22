#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Agent-E2E flow F25: a ``/learn/...`` launch leaves ONE tutor window (C4).

``tutor --route /learn/S/M`` launches Chrome on the profile a tutor window
already runs, so Chrome opens a SECOND ``--app`` window. A used window can
never close itself (a page may only while its history has one entry), so
the new one hands its route to the old one and closes itself before Flutter
boots (``web/index.html``). Real ``--app`` windows on one profile:

1. the old window opens on ``#/plan/S`` and navigates once inside the app,
   as a used window has (``history.length`` > 1);
2. a second Chrome on the same profile opens ``#/learn/S/M`` and hands the
   URL to the running one;
3. exactly one app window is left, the old one, and it shows the learn
   session (its ``session_start`` names M; a live session on M is reused,
   never lost).

Run through ``e2e_drive.py``: ``up --phase "theory S/M"``, ``flow F25``.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from typing import TYPE_CHECKING, Any

from e2e_cdp import Browser, CdpError
from e2e_flow import Flow, FlowError

if TYPE_CHECKING:
    from pathlib import Path

LC = "leetcode-easy-algorithms-in-typescript"
MODULE = "prefix-sums"
LOCK = "Not teachable now"  # the plan tile's lock glyph, spoken


class AppBrowser(Browser):
    """A :class:`Browser` that can see and switch between its app windows."""

    def app_pages(self, origin: str) -> list[dict[str, Any]]:
        """The page targets on ``origin`` (one per open app window)."""
        infos = self.call("Target.getTargets", root=True)["targetInfos"]
        return [t for t in infos if t["type"] == "page" and t["url"].startswith(origin)]

    def windows(self, pages: list[dict[str, Any]]) -> set[int]:
        """The distinct browser windows holding ``pages``."""
        return {
            int(
                self.call(
                    "Browser.getWindowForTarget", root=True, targetId=p["targetId"]
                )["windowId"]
            )
            for p in pages
        }

    @property
    def profile(self) -> Path:
        """The scratch profile a second launch must share."""
        return self._profile

    @property
    def binary(self) -> str:
        """The Chrome binary the first window runs."""
        return str(self._proc.args[0])


def text_below(browser: Browser, text: str, timeout: float) -> bool:
    """Wait for ``text`` in any label, scrolling down (the plan's tiles are lazy).

    A module tile speaks one merged label (``ready · Not teachable now · ...``).
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if text in browser.page_text():
            return True
        browser.scroll(600)
        time.sleep(1)
    return False


def _second_launch(flow: Flow, browser: AppBrowser, url: str) -> None:
    """``chromium --app=url`` on the running profile, as ``tutor --route`` does."""
    flow.step(f"a second Chrome on the same profile opens {url.split('#')[1]}")
    env = {
        **os.environ,
        "DISPLAY": flow.args.display,
        "XDG_CONFIG_HOME": str(browser.profile),
    }
    started = time.monotonic()
    done = subprocess.run(  # the handoff: it exits once the running Chrome has the URL
        [
            browser.binary,
            f"--user-data-dir={browser.profile}",
            "--disable-extensions",
            "--mute-audio",
            f"--app={url}",
        ],
        env=env,
        capture_output=True,
        timeout=20,
        check=False,
    )
    took = time.monotonic() - started
    flow.note(f"second chrome exited {done.returncode} after {took:.1f} s")


def _one_window_left(flow: Flow, browser: AppBrowser, old: str) -> dict[str, Any]:
    """Wait until one app window is left; it must be ``old``."""
    flow.step("exactly one tutor window is left, the old one")
    origin = flow.args.app.split("/app/")[0]
    deadline = time.monotonic() + 20
    pages: list[dict[str, Any]] = []
    while time.monotonic() < deadline:
        pages = browser.app_pages(origin)
        if len(pages) == 1 and pages[0]["targetId"] == old:
            break
        time.sleep(0.5)
    shown = [(p["targetId"][:8], p["url"][-60:]) for p in pages]
    flow.note(f"app pages: {shown}; windows: {len(browser.windows(pages))}")
    if len(pages) != 1 or pages[0]["targetId"] != old:
        msg = (
            f"want only the old app window, have {len(pages)}: {shown} (old {old[:8]})"
        )
        raise FlowError(msg)
    return pages[0]


def _stops(flow: Flow, sid: object) -> int:
    """``stop`` events in session ``sid``'s transcript (-1: no transcript)."""
    path = flow.args.data / "sessions" / f"{sid}.jsonl"
    if not sid or not path.is_file():
        return -1
    lines = path.read_text(encoding="utf-8").splitlines()
    return sum(json.loads(line).get("type") == "stop" for line in lines if line)


def _learn_request(flow: Flow, before: set[str], live: dict[str, Any]) -> None:
    """The window asked to teach MODULE; the session live before is not lost.

    It stays open (no ``stop`` lands in its transcript), so Continue resumes
    it on the server; F21 proves a live session on MODULE is reused.
    """
    flow.step(f"the window sent session_start for {LC}/{MODULE}")
    stops = _stops(flow, live.get("session"))
    rid = flow.request("session_start", before)
    body = (flow.db.node(f"requests/{rid}").get("req") or {}).get("body") or {}
    flow.note(f"body={json.dumps(body)[:200]} live before={live}")
    if body.get("subject") != LC or body.get("module") != MODULE:
        msg = f"session_start body {body}, want {LC}/{MODULE}"
        raise FlowError(msg)
    started = (flow.result("session_start", before).get("data") or {}).get("session")
    flow.step(f"session {started}; the one live before ({live.get('session')}) kept")
    if (after := _stops(flow, live.get("session"))) != stops:
        msg = f"the session live before got stopped ({stops} -> {after} stops)"
        raise FlowError(msg)


def f25(flow: Flow) -> None:
    """The window takeover (module doc)."""
    browser = flow.browser
    if not isinstance(browser, AppBrowser):
        msg = "F25 needs an AppBrowser"
        raise FlowError(msg)
    flow.step(f"the old window shows {LC}'s plan")
    if not text_below(browser, LOCK, 40):
        msg = f"no plan screen; saw: {browser.page_text()[:300]!r}"
        raise FlowError(msg)
    flow.tap("Back")  # one in-app navigation, as a used window has
    time.sleep(1)
    length = browser.evaluate("history.length")
    flow.note(f"old window history.length={length}")
    old = browser.app_pages(flow.args.app.split("/app/")[0])[0]["targetId"]
    live, before = flow.db.node("live"), flow.rids()
    _second_launch(
        flow, browser, f"{flow.args.app}?db={flow.args.db}#/learn/{LC}/{MODULE}"
    )
    _one_window_left(flow, browser, old)
    _learn_request(flow, before, live)
    flow.step("the old window now shows the learn session (composer up)")
    try:
        found = browser.wait_for("Your answer", 30)
    except CdpError as err:
        msg = f"cannot read the new window: {err}"
        raise FlowError(msg) from err
    if found is None:
        msg = f"no session composer; saw: {browser.page_text()[:300]!r}"
        raise FlowError(msg)
    flow.shot("takeover")
