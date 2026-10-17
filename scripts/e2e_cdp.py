#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""A stdlib-only Chrome DevTools Protocol client over ``--remote-debugging-pipe``.

Chrome reads NUL-terminated JSON commands from fd 3 and writes replies and
events to fd 4, so no port is opened and no websocket library is needed.
Chrome runs headed on a virtual X display (never kuhy's ``:0``): CanvasKit
renders blank in headless mode. Flutter web exposes its semantics tree as
DOM nodes, so :meth:`Browser.find` locates a button by its label and
:meth:`Browser.click` taps the centre of its box with real mouse events.
"""

from __future__ import annotations

import base64
import json
import logging
import os
from pathlib import Path
import select
import shutil
import subprocess
import tempfile
import time
from typing import Any, Final, Self

_logger = logging.getLogger(__name__)
_BROWSERS: Final = ("/usr/bin/chromium", "/usr/bin/google-chrome-stable")
# find(label) / text(), run in the page (labels of Flutter's semantics DOM).
_PAGE_JS: Final = Path(__file__).with_name("e2e_page.js").read_text(encoding="utf-8")


class CdpError(RuntimeError):
    """Chrome answered a command with an error, or never answered."""


def _browser() -> str:
    for path in _BROWSERS:
        if Path(path).is_file():
            return path
    msg = "no chromium or google-chrome binary"
    raise CdpError(msg)


class Browser:
    """One Chrome window on ``display`` with a scratch profile."""

    def __init__(
        self, display: str, log: Path, size: tuple[int, int] = (1366, 768)
    ) -> None:
        """Start Chrome (stderr to ``log``) and attach to its first page."""
        log.parent.mkdir(parents=True, exist_ok=True)
        self._log = log.open("wb")
        self._profile = Path(tempfile.mkdtemp(prefix="tutor-e2e-chrome."))
        cmd_r, self._cmd_w = os.pipe()
        self._out_r, out_w = os.pipe()

        def wire_fds() -> None:
            os.dup2(cmd_r, 3)
            os.dup2(out_w, 4)

        env = {**os.environ, "DISPLAY": display, "XDG_CONFIG_HOME": str(self._profile)}
        self._proc = subprocess.Popen(
            [
                _browser(),
                "--remote-debugging-pipe",
                f"--user-data-dir={self._profile}",
                "--disable-extensions",
                "--no-first-run",
                "--no-default-browser-check",
                "--password-store=basic",
                "--window-position=0,0",
                f"--window-size={size[0]},{size[1]}",
                "--force-device-scale-factor=1",
                "about:blank",
            ],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=self._log,
            preexec_fn=wire_fds,
            pass_fds=(3, 4),
        )
        os.close(cmd_r)
        os.close(out_w)
        self._buf = b""
        self._next = 0
        self.problems: list[str] = []
        self._session = ""
        pages = [
            t
            for t in self.call("Target.getTargets", root=True)["targetInfos"]
            if t["type"] == "page"
        ]
        attached = self.call(
            "Target.attachToTarget",
            root=True,
            targetId=pages[0]["targetId"],
            flatten=True,
        )
        self._session = attached["sessionId"]
        # --window-size is ignored without a window manager; size it over CDP.
        window = self.call(
            "Browser.getWindowForTarget", root=True, targetId=pages[0]["targetId"]
        )
        self.call(
            "Browser.setWindowBounds",
            root=True,
            windowId=window["windowId"],
            bounds={"left": 0, "top": 0, "width": size[0], "height": size[1]},
        )

    def __enter__(self) -> Self:
        """Context use closes Chrome and its profile."""
        return self

    def __exit__(self, *_: object) -> None:
        """Close Chrome and delete the profile."""
        self._proc.terminate()
        try:
            self._proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _logger.warning("chrome ignored SIGTERM for 5 s; killing it")
            self._proc.kill()
        os.close(self._cmd_w)
        os.close(self._out_r)
        self._log.close()
        shutil.rmtree(self._profile, ignore_errors=True)

    def _read(self, deadline: float) -> dict[str, Any]:
        while b"\0" not in self._buf:
            left = deadline - time.monotonic()
            if left <= 0 or not select.select([self._out_r], [], [], left)[0]:
                msg = "chrome did not answer in time"
                raise CdpError(msg)
            chunk = os.read(self._out_r, 1 << 20)
            if not chunk:
                msg = "chrome closed the debugging pipe"
                raise CdpError(msg)
            self._buf += chunk
        raw, self._buf = self._buf.split(b"\0", 1)
        message: dict[str, Any] = json.loads(raw)
        return message

    def call(
        self, method: str, *, root: bool = False, **params: object
    ) -> dict[str, Any]:
        """Send one command (to the page unless ``root``) and return its result."""
        self._next += 1
        msg: dict[str, Any] = {"id": self._next, "method": method, "params": params}
        if self._session and not root:
            msg["sessionId"] = self._session
        try:
            os.write(self._cmd_w, json.dumps(msg).encode() + b"\0")
        except BrokenPipeError:
            msg_ = f"chrome exited (code {self._proc.poll()}); see {self._log.name}"
            raise CdpError(msg_) from None
        deadline = time.monotonic() + 30
        while True:
            reply = self._read(deadline)
            self._note(reply)
            if reply.get("id") == self._next:
                if "error" in reply:
                    msg = f"{method}: {reply['error']}"
                    raise CdpError(msg)
                result: dict[str, Any] = reply.get("result", {})
                return result

    def evaluate(self, expression: str) -> object:
        """The JSON value of ``expression`` in the page."""
        out = self.call("Runtime.evaluate", expression=expression, returnByValue=True)
        return out.get("result", {}).get("value")

    def _note(self, event: dict[str, Any]) -> None:
        """Keep the page's console errors and uncaught exceptions."""
        params = event.get("params", {})
        if event.get("method") == "Runtime.exceptionThrown":
            detail = params.get("exceptionDetails", {})
            self.problems.append(
                f"exception: {detail.get('exception', {}).get('description', detail)}"
            )
        elif event.get("method") == "Runtime.consoleAPICalled" and params.get(
            "type"
        ) in {"error", "warning"}:
            args = " ".join(
                str(a.get("value", a.get("description"))) for a in params["args"]
            )
            self.problems.append(f"console.{params['type']}: {args}")

    def open(self, url: str) -> None:
        """Navigate the page (console errors are kept in :attr:`problems`)."""
        self.call("Runtime.enable")
        self.call("Page.enable")
        self.call("Page.navigate", url=url)

    def find(self, label: str) -> dict[str, Any] | None:
        """The centre and text of the first node labelled ``label`` (or prefix)."""
        hit = self.evaluate(f"({_PAGE_JS}).find({json.dumps(label)})")
        return hit if isinstance(hit, dict) else None

    def wait_for(self, label: str, timeout: float) -> dict[str, Any] | None:
        """Poll :meth:`find` until it hits or ``timeout`` passes."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if hit := self.find(label):
                return hit
            time.sleep(0.25)
        return None

    def page_text(self) -> str:
        """Every semantics label on the page, one per line."""
        text = self.evaluate(f"({_PAGE_JS}).text()")
        return text if isinstance(text, str) else ""

    def click(self, hit: dict[str, Any]) -> None:
        """A real left click (move, press, release) at ``hit``'s centre."""
        point = {"x": hit["x"], "y": hit["y"]}
        self.call("Input.dispatchMouseEvent", type="mouseMoved", **point)
        for kind in ("mousePressed", "mouseReleased"):
            self.call(
                "Input.dispatchMouseEvent",
                type=kind,
                button="left",
                clickCount=1,
                **point,
            )

    def scroll(self, dy: float) -> None:
        """A mouse-wheel scroll of ``dy`` px at the viewport's centre."""
        size = self.evaluate("[innerWidth, innerHeight]")
        width, height = size if isinstance(size, list) else (800, 600)
        self.call(
            "Input.dispatchMouseEvent",
            type="mouseWheel",
            x=width / 2,
            y=height / 2,
            deltaX=0,
            deltaY=dy,
        )

    def screenshot(self, out: Path) -> Path:
        """Save the viewport as PNG."""
        out.parent.mkdir(parents=True, exist_ok=True)
        data = self.call("Page.captureScreenshot", format="png")["data"]
        out.write_bytes(base64.b64decode(data))
        return out
