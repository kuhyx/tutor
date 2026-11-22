#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Agent-E2E flow F27: a ``/learn/...`` launch SHOWS the tutor under i3 (C4).

The LeetCode lock's learn button runs ``tutor --route /learn/S/M`` while kuhy
looks at the lock, so the tutor must be on screen at once. F26 proves the
launch is handed to the tutor window already open; i3 may hold that window on
a workspace that is not shown, and a page cannot raise itself there. On a
private Xvfb with its own i3 on kuhy's config (``e2e_i3_handover.sh``):

1. the old tutor window opens on workspace 2 and shows the plan;
2. workspace 1 is shown and focused, as when kuhy works elsewhere;
3. ``run.sh --route /learn/S/M`` (what ``~/.local/bin/tutor`` execs) runs
   against the sandbox server and the old window's profile;
4. the app sent ``session_start`` for S/M, one tutor window is left and the
   focused, visible workspace holds it.

Every i3 fact is read from the nested i3's own socket, never kuhy's. Run by
``scripts/e2e_i3_handover.sh`` after ``e2e_sandbox.sh up --phase "theory
S/M"``; the Xvfb root is saved to ``--shot``, pass or fail.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from functools import partial
import json
import logging
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from typing import TYPE_CHECKING, Any, Final
from urllib.parse import urlsplit

from e2e_cdp import CdpError
from e2e_flow import Flow, FlowError
from e2e_follow_up import COMPOSER
from e2e_takeover import LC, LOCK, MODULE, AppBrowser, text_below

if TYPE_CHECKING:
    from collections.abc import Iterator

_logger = logging.getLogger(__name__)
RUN_SH: Final = Path(__file__).resolve().parents[1] / "run.sh"
ROUTE: Final = f"/learn/{LC}/{MODULE}"
TUTOR: Final = "tutor"  # run.sh's --class: the WM_CLASS i3 reads
PARKED: Final = "2"  # the old window's workspace
SHOWN: Final = "1"  # the workspace kuhy looks at
BUDGET: Final = 40.0  # seconds for every wait together: one call stays < 60 s
# Run a command to its end; the caller reads the exit code.
_run: Final = partial(
    subprocess.run, capture_output=True, text=True, timeout=20, check=False
)


def left(flow: Flow, cap: float) -> float:
    """Seconds a wait may take: ``cap``, or what is left of the budget."""
    return max(1.0, min(cap, flow.args.deadline - time.monotonic()))


@dataclass(frozen=True)
class Facts:
    """Where i3 holds the tutor windows and which workspace kuhy looks at."""

    tutors: tuple[str, ...]  # the workspace of each tutor window
    urgent: bool  # a tutor window carries the urgency hint
    focused: str  # the focused workspace
    visible: tuple[str, ...]  # every workspace on an output

    @property
    def on_screen(self) -> bool:
        """One tutor window, on the focused and visible workspace."""
        return self.tutors == (self.focused,) and self.focused in self.visible


def _tutors(node: dict[str, Any], workspace: str = "") -> Iterator[tuple[str, bool]]:
    """(workspace, urgent) of every tutor window under ``node``."""
    if node.get("type") == "workspace":
        workspace = str(node.get("name"))
    if (node.get("window_properties") or {}).get("class") == TUTOR:
        yield workspace, bool(node.get("urgent"))
    for child in (*node.get("nodes", ()), *node.get("floating_nodes", ())):
        yield from _tutors(child, workspace)


class I3:
    """The nested i3, asked over its own socket."""

    def __init__(self, sock: str) -> None:
        """Bind ``i3-msg`` to ``sock``."""
        self._msg = [shutil.which("i3-msg") or "i3-msg", "-s", sock]

    def _call(self, *args: str) -> str:
        done = _run([*self._msg, *args])
        if done.returncode != 0:
            msg = f"i3-msg {args}: {done.stdout.strip()} {done.stderr.strip()}"
            raise FlowError(msg)
        return done.stdout

    def show(self, workspace: str) -> None:
        """Switch to ``workspace``."""
        self._call(f"workspace number {workspace}")

    def facts(self) -> Facts:
        """The tree and the workspaces, as i3 reports them now."""
        tutors = list(_tutors(json.loads(self._call("-t", "get_tree"))))
        spaces = json.loads(self._call("-t", "get_workspaces"))
        return Facts(
            tutors=tuple(workspace for workspace, _ in tutors),
            urgent=any(urgent for _, urgent in tutors),
            focused=next((str(w["name"]) for w in spaces if w["focused"]), ""),
            visible=tuple(str(w["name"]) for w in spaces if w["visible"]),
        )


def park(flow: Flow, i3: I3) -> None:
    """The old window on its workspace; kuhy looks at another one."""
    flow.step(f"the old tutor window shows {LC}'s plan on workspace {PARKED}")
    if not text_below(flow.browser, LOCK, left(flow, 25)):
        msg = f"no plan screen; saw: {flow.browser.page_text()[:300]!r}"
        raise FlowError(msg)
    flow.step(f"workspace {SHOWN} is shown and focused, the window stays on {PARKED}")
    i3.show(SHOWN)
    facts = i3.facts()
    flow.note(str(facts))
    if facts.tutors != (PARKED,) or facts.focused != SHOWN or PARKED in facts.visible:
        msg = f"PRECONDITION: want one tutor window, on hidden workspace {PARKED}"
        raise FlowError(msg)


def launch(flow: Flow, browser: AppBrowser, scratch: Path) -> None:
    """``run.sh --route``: the sandbox port, the old window's profile, muted."""
    flow.step(f"run.sh --route {ROUTE} (what ~/.local/bin/tutor execs)")
    chromium = scratch / "chromium"  # TUTOR_BROWSER takes a command, no flags
    chromium.write_text(
        f'#!/bin/sh\nexec "{browser.binary}" --disable-extensions --mute-audio "$@"\n',
        encoding="utf-8",
    )
    chromium.chmod(chromium.stat().st_mode | stat.S_IXUSR)
    env = {
        **os.environ,
        "DISPLAY": flow.args.display,
        "I3SOCK": flow.args.sock,
        "TUTOR_DESKTOP_PORT": str(urlsplit(flow.args.app).port),
        "TUTOR_DESKTOP_PROFILE": str(browser.profile),
        "TUTOR_BROWSER": str(chromium),
    }
    done = _run([str(RUN_SH), "--route", ROUTE], env=env)
    flow.note(f"exit {done.returncode}: {done.stdout.strip()} {done.stderr.strip()}")
    if done.returncode != 0:
        msg = "run.sh failed"
        raise FlowError(msg)


def judge(flow: Flow, i3: I3, before: set[str]) -> list[str]:
    """What is wrong after the launch (nothing: kuhy sees the session)."""
    wrong: list[str] = []
    try:
        rid = flow.request("session_start", before, left(flow, 10))
    except FlowError as err:
        _logger.warning("  %s", err)
        wrong.append(f"{err} (the window never opened {ROUTE})")
    else:
        body = (flow.db.node(f"requests/{rid}").get("req") or {}).get("body") or {}
        flow.note(f"body={json.dumps(body)[:200]}")
        if body.get("subject") != LC or body.get("module") != MODULE:
            wrong.append(f"session_start body {body}, want {LC}/{MODULE}")
    flow.step("one tutor window is left, on the focused and visible workspace")
    deadline = time.monotonic() + left(flow, 8)
    while not i3.facts().on_screen and time.monotonic() < deadline:
        time.sleep(0.5)
    time.sleep(2)  # the launch's own window gives up after 1 s: judge what stays
    facts = i3.facts()
    flow.note(str(facts))
    if len(facts.tutors) != 1:
        wrong.append(f"{len(facts.tutors)} tutor windows, want 1")
    if not facts.on_screen:
        wrong.append(
            f"the tutor is on workspace {'+'.join(facts.tutors) or '?'}, kuhy looks "
            f"at {facts.focused} (urgency hint: {facts.urgent})"
        )
    return wrong


def root_shot(flow: Flow) -> None:
    """Save the Xvfb root, what kuhy would see, to ``--shot``."""
    out = Path(flow.args.shot)
    out.parent.mkdir(parents=True, exist_ok=True)
    grab = shutil.which("import") or "import"  # imagemagick
    _run([grab, "-display", flow.args.display, "-window", "root", str(out)], check=True)
    _logger.info("%s screenshot: %s", flow.args.flow, out)


def drive(args: argparse.Namespace) -> list[str]:
    """Run the flow; what is wrong at its end."""
    args.deadline = time.monotonic() + BUDGET
    i3 = I3(args.sock)
    i3.show(PARKED)
    plan, log = f"{args.app}?db={args.db}#/plan/{LC}", Path(f"{args.shot}.chrome.log")
    with (
        AppBrowser(args.display, log, (1600, 900), app=plan) as browser,
        tempfile.TemporaryDirectory(prefix="tutor-e2e-i3.") as scratch,
    ):
        flow = Flow(args, browser)
        try:
            park(flow, i3)
            before = flow.rids()
            launch(flow, browser, Path(scratch))
            wrong = judge(flow, i3, before)
            if not wrong:
                flow.step("the window shows the session (composer up)")
                seen = browser.wait_for(COMPOSER, left(flow, 20))
                flow.note("composer up" if seen else "not yet: the tutor still thinks")
        except (FlowError, CdpError, OSError, subprocess.SubprocessError) as err:
            _logger.warning("  step %d: %s", flow.n, err)
            wrong = [f"step {flow.n}: {err}"]
        finally:
            shutil.rmtree(f"{browser.profile}.xdg", ignore_errors=True)  # run.sh's
            root_shot(flow)
    return wrong


def main() -> int:
    """CLI entry (see the module docstring)."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", required=True, help="http://127.0.0.1:N/app/")
    parser.add_argument("--db", required=True, help="emulator http://127.0.0.1:N")
    parser.add_argument("--display", required=True, help="the private Xvfb, :N")
    parser.add_argument("--sock", required=True, help="the nested i3's socket")
    parser.add_argument("--shot", required=True, help="where the Xvfb root goes")
    args = parser.parse_args(namespace=argparse.Namespace(flow="F27"))
    if args.display.split(".")[0] == ":0":
        parser.error("never kuhy's display :0")
    logging.basicConfig(stream=sys.stdout, format="%(message)s", level=logging.INFO)
    wrong = drive(args)
    for line in wrong:
        _logger.warning("FAIL %s: %s", args.flow, line)
    if not wrong:
        _logger.info("PASS %s", args.flow)
    return 1 if wrong else 0


if __name__ == "__main__":
    raise SystemExit(main())
