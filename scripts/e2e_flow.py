#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Shared agent-E2E steps: the emulator view and the step logger (``Flow``).

Used by ``scripts/e2e_drive.py`` (F1, F2) and ``scripts/e2e_follow_up.py``
(F3, F4).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
import time
from typing import TYPE_CHECKING, Any
import urllib.request

if TYPE_CHECKING:
    import argparse

    from e2e_cdp import Browser

_logger = logging.getLogger(__name__)
# Call-to-action labels of the session screen's blocked panel.
BLOCKED_CTAS = ("Learn more anyway", "Review this subject")
# What a phased flow's send step hands its check step (JSON on disk).
State = dict[str, Any]


class FlowError(RuntimeError):
    """A flow step saw something other than what it expects."""


class Emulator:
    """Read-only REST view of the sandbox RTDB (``/tutor/v1``)."""

    def __init__(self, url: str) -> None:
        """Bind the emulator base URL (``http://127.0.0.1:N``)."""
        self.url = url.rstrip("/")

    def get(self, path: str) -> object:
        """The JSON at ``path`` (``None`` if absent)."""
        with urllib.request.urlopen(
            f"{self.url}/tutor/v1/{path}.json", timeout=10
        ) as r:
            value: object = json.load(r)
            return value

    def node(self, path: str) -> dict[str, Any]:
        """The object at ``path``; ``{}`` when absent or not an object."""
        value = self.get(path)
        return value if isinstance(value, dict) else {}


class Flow:
    """Shared steps; ``step`` logs before each one runs."""

    def __init__(self, args: argparse.Namespace, browser: Browser) -> None:
        """Keep the run's arguments, browser and emulator."""
        self.args, self.browser, self.db = args, browser, Emulator(args.db)
        self.n = 0

    def step(self, what: str) -> None:
        """Print the next step's number and goal."""
        self.n += 1
        print(f"{self.args.flow} step {self.n}: {what}", flush=True)

    def shot(self, suffix: str) -> Path:
        """Save a screenshot as ``<out>_<suffix>.png`` and print its path."""
        out = self.browser.screenshot(Path(f"{self.args.out}_{suffix}.png"))
        print(f"{self.args.flow} screenshot: {out}", flush=True)
        return out

    def tap(self, label: str, timeout: float = 20) -> None:
        """Wait for the node labelled ``label``, scroll it on screen, click it."""
        self.step(f'tap "{label}"')
        hit = self.browser.wait_for(label, timeout)
        for _ in range(5):
            if hit is None or hit["visible"]:
                break
            self.browser.scroll(300 if hit["below"] else -300)
            time.sleep(0.5)
            hit = self.browser.find(label)
        if hit is None or not hit["visible"]:
            msg = f'no "{label}" on screen; saw: {self.browser.page_text()[:400]!r}'
            raise FlowError(msg)
        self.browser.click(hit)

    def precheck(self, *, capped: bool) -> None:
        """Today's new count vs the effective cap, as the worker published it."""
        self.step("precondition: stats.today and prefs from the emulator")
        today = self.db.node("stats").get("today") or {}
        prefs = self.db.node("prefs")
        new, cap = today.get("new"), today.get("new_cap")
        print(
            f"  today.new={new} new_cap={cap} prefs={prefs} live={self.db.get('live')}"
        )
        if not isinstance(new, int) or not isinstance(cap, int):
            msg = "stats.today has no new / new_cap (worker not up?)"
            raise FlowError(msg)
        if capped != (new >= cap):
            want = "new >= cap" if capped else "new < cap"
            msg = f"PRECONDITION: want {want}, have new={new} cap={cap}"
            raise FlowError(msg)

    def start_result(self, since: set[str], timeout: float = 45) -> dict[str, Any]:
        """The first new ``session_start`` request's result."""
        self.step("wait for the worker's session_start result")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for rid, node in sorted(self.db.node("requests").items()):
                req = node.get("req") or {}
                if rid in since or req.get("kind") != "session_start":
                    continue
                if result := node.get("result"):
                    shown = json.dumps(result)[:300]
                    print(f"  rid={rid} body={req.get('body')} result={shown}")
                    return dict(result)
            time.sleep(0.5)
        msg = f"no session_start result in {timeout:.0f} s"
        raise FlowError(msg)

    def rids(self) -> set[str]:
        """Request ids present now."""
        return set(self.db.node("requests"))

    def expect_card(self) -> None:
        """``live.card`` is ``--card`` and its first tutor message is on screen."""
        self.step(f"live card is {self.args.card} with a tutor message")
        live = self.db.node("live")
        if live.get("card") != self.args.card:
            msg = f"live={live}, want card {self.args.card}"
            raise FlowError(msg)
        msgs = self.db.node(f"sessions/{live['session']}/msgs")
        tutor = [m for _, m in sorted(msgs.items()) if m.get("role") == "tutor"]
        if not tutor:
            msg = f"session {live['session']} has no tutor message"
            raise FlowError(msg)
        line = str(tutor[0].get("text", "")).strip().splitlines()[0]
        print(f"  session={live['session']} first tutor line: {line[:160]}")
        # Message bodies are selectable markdown with no semantics label, so
        # the screen check is: the composer is up and no blocked panel shows.
        self.step("the session screen is open with no blocked panel")
        if self.browser.wait_for("Send", 15) is None:
            msg = f"no composer; saw: {self.browser.page_text()[:400]!r}"
            raise FlowError(msg)
        time.sleep(2)
        if hits := [b for b in BLOCKED_CTAS if b in self.browser.page_text()]:
            msg = f"blocked panel still shown: {hits}"
            raise FlowError(msg)

    def result(self, kind: str, since: set[str], timeout: float = 50) -> dict[str, Any]:
        """The result of the first new ``kind`` request after ``since``."""
        self.step(f"wait for the worker's {kind} result")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for rid, node in sorted(self.db.node("requests").items()):
                req = node.get("req") or {}
                if rid in since or req.get("kind") != kind:
                    continue
                if found := node.get("result"):
                    print(f"  rid={rid} result={json.dumps(found)[:300]}")
                    return dict(found)
            time.sleep(0.5)
        msg = f"no {kind} result in {timeout:.0f} s"
        raise FlowError(msg)

    def request(self, kind: str, since: set[str], timeout: float = 20) -> str:
        """The id of the first new ``kind`` request after ``since`` (sent, any state).

        A phased flow's send step ends here: the worker reads the request
        from the emulator, so the browser may close before the reply.
        """
        self.step(f"the app sent a {kind} request")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for rid, node in sorted(self.db.node("requests").items()):
                if rid not in since and (node.get("req") or {}).get("kind") == kind:
                    print(f"  rid={rid}")
                    return str(rid)
            time.sleep(0.5)
        msg = f"no {kind} request in {timeout:.0f} s"
        raise FlowError(msg)

    def result_of(self, rid: str) -> dict[str, Any]:
        """Request ``rid``'s result (``{}`` while the worker is still on it)."""
        return self.db.node(f"requests/{rid}/result")

    def type_into(self, label: str, text: str) -> None:
        """Focus the field labelled ``label`` and type ``text`` into it."""
        self.tap(label)
        time.sleep(0.5)
        self.step(f"type {text!r}")
        self.browser.type_text(text)
        time.sleep(0.5)

    def expect(self, *labels: str, timeout: float = 15) -> None:
        """Every one of ``labels`` is on screen (else a ``FlowError``)."""
        self.step(f"on screen: {', '.join(labels)}")
        for label in labels:
            if self.browser.wait_for(label, timeout) is None:
                msg = f"no {label!r}; saw: {self.browser.page_text()[:400]!r}"
                raise FlowError(msg)

    def screen(self, route: str) -> None:
        """Open the app on ``route`` (``app/lib/ui/nav.dart``)."""
        self.step(f"open the app on {route}")
        self.browser.open(f"{self.args.app}?db={self._page_db()}&screen={route}")

    def _page_db(self) -> str:
        """The app's database: the h2 proxy (``--app-db``), else the emulator."""
        return str(getattr(self.args, "app_db", None) or self.args.db)

    def home(self) -> None:
        """Open the app on Home."""
        self.step(f"open {self.args.app}")
        self.browser.open(f"{self.args.app}?db={self._page_db()}")
