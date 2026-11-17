#!/usr/bin/python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Driver for scripts/e2e_evening_gate.sh: seed, probe, and scripted clicks.

``seed``   append one signed credit row (today) to the sandbox ledger.
``probe``  print which gatelock claims hold the X grab right now.
``end`` / ``study`` / ``study-credit``  run the real gate (real HARD lock, real
Arbiter, real global grab) on the private Xvfb in $DISPLAY and click its
controls with xdotool THROUGH the grab, in the steps of PLANS. The gate's exit
code is printed as ``EXIT=<n>``; a failed expectation prints ``FAIL`` and exits
97 (the grab dies with the process).

Never run against a real display: $DISPLAY must be a private Xvfb (not :0).
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import TYPE_CHECKING, ClassVar

import earned_time
import gatelock

from tutor import gate, gate_lock, gate_view

if TYPE_CHECKING:
    from collections.abc import Callable
    import tkinter as tk

ROOT = Path(os.environ.get("E2E_DIR", "."))
SHOTS = ROOT / "shots"
OPENED = ROOT / "opened.txt"
TUTOR_URL = "http://127.0.0.1:8778/app/"
WATCHDOG_MS = 30_000
EXIT_FAIL = 97


def say(line: str) -> None:
    """One evidence line on stdout."""
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def seed(minutes: int, number: int) -> None:
    """Append a signed row paying ``minutes`` that ended just now."""
    ledger = Path(os.environ["TUTOR_DATA"]) / "ledger.json"
    key = Path(os.environ["TUTOR_KEY"]).read_bytes().strip()
    rows = json.loads(ledger.read_text())["entries"] if ledger.exists() else []
    now = datetime.now(tz=UTC)
    row: dict[str, object] = {
        "kind": "credit",
        "entry_id": f"e2e-m{number}",
        "day": now.astimezone().date().isoformat(),
        "detail": {"minutes": minutes, "ended_at": now.timestamp()},
    }
    row["hmac"] = earned_time.entry_signature(row, key)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(json.dumps({"entries": [*rows, row]}))


def quota() -> int:
    """Today's full quota in minutes."""
    return earned_time.tutor_quota_for(datetime.now().astimezone().date()) or 60


def probe() -> None:
    """Print the apps whose grab is actually held."""
    held = ",".join(c.app for c in gatelock.held_grabs())
    say(f"held={held}")


def fail(message: str) -> None:
    """Report a failed expectation and die (releases the grab)."""
    say(f"FAIL {message}")
    os._exit(EXIT_FAIL)


def grab_held() -> bool:
    """Ask a SEPARATE process whether tutor_gate holds the grab."""
    out = subprocess.run(
        [sys.executable, __file__, "probe"], capture_output=True, text=True, check=True
    ).stdout
    return "tutor_gate" in out


def shot(label: str) -> None:
    """Full-root screenshot of the private display."""
    SHOTS.mkdir(parents=True, exist_ok=True)
    target = SHOTS / f"{label}.png"
    subprocess.run(["/usr/bin/import", "-window", "root", str(target)], check=True)
    say(f"shot {target}")


def click(widget: tk.Misc) -> None:
    """A real X click on the centre of ``widget`` (goes through the grab)."""
    widget.update_idletasks()
    x = widget.winfo_rootx() + widget.winfo_width() // 2
    y = widget.winfo_rooty() + widget.winfo_height() // 2
    subprocess.run(
        ["/usr/bin/xdotool", "mousemove", str(x), str(y), "click", "1"], check=True
    )
    say(f"click {x},{y}")


def expect(*, ok: bool, message: str) -> None:
    """Fail the run unless ``ok``."""
    say(("ok   " if ok else "BAD  ") + message)
    if not ok:
        fail(message)


class Scripted(gate_lock.EveningLock):
    """The production lock, plus a timed list of steps run on its Tk loop."""

    plan: ClassVar[list[tuple[int, Callable[[Scripted], None]]]] = []

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Arm the real lock, then start the plan and the watchdog."""
        super().__init__(*args, **kwargs)
        self.steps = list(type(self).plan)
        self.root.after(WATCHDOG_MS, lambda: fail("watchdog: gate never exited"))
        self.root.after(self.steps[0][0], self._next)

    def _next(self) -> None:
        _, step = self.steps.pop(0)
        step(self)
        if self.steps:
            self.root.after(self.steps[0][0], self._next)

    def panel(self) -> gate_view.Panel:
        """The primary surface's panel."""
        return next(iter(self.panels.values()))


def at_t0(lock: Scripted, label: str) -> None:
    """The grab is really held and both controls exist at t=0."""
    expect(ok=grab_held(), message="t=0: tutor_gate holds the X grab")
    panel = lock.panel()
    mapped = panel.open_button.winfo_ismapped() and panel.end_button.winfo_ismapped()
    expect(ok=bool(mapped), message="t=0: open and end controls are mapped")
    shot(label)


def end_click(lock: Scripted) -> None:
    """Click end-evening under the grab."""
    click(lock.panel().end_button)


def open_click(lock: Scripted) -> None:
    """Click open-tutor under the grab, from t=0."""
    OPENED.unlink(missing_ok=True)
    click(lock.panel().open_button)


def studying(lock: Scripted, label: str) -> None:
    """Grab released, browser opener got the URL, strip is up."""
    expect(ok=not grab_held(), message="study: the grab is released")
    url = OPENED.read_text().strip() if OPENED.exists() else ""
    expect(ok=url == TUTOR_URL, message=f"study: opened {url!r}")
    expect(ok=lock.strip is not None, message="study: the strip is up")
    shot(label)


def back_click(lock: Scripted) -> None:
    """Click the strip's back control (no grab is held now)."""
    if lock.strip is None:
        fail("no strip to click")
        return
    click(lock.strip.back_button)


def relocked(lock: Scripted) -> None:
    """After back: grab held again, strip gone."""
    expect(ok=grab_held(), message="back: the grab is held again")
    expect(ok=lock.strip is None, message="back: the strip is gone")
    shot("study-back")


def credit_now(_lock: Scripted) -> None:
    """The credit lands from outside (the tutor's writer) while studying."""
    seed(quota(), 99)
    say("seeded full credit")


PLANS: dict[str, list[tuple[int, Callable[[Scripted], None]]]] = {
    "end": [
        (1500, lambda lk: at_t0(lk, "end-t0")),
        (200, end_click),
    ],
    "study": [
        (1500, lambda lk: at_t0(lk, "study-t0")),
        (200, open_click),
        (2000, lambda lk: studying(lk, "study-open")),
        (200, back_click),
        (2500, relocked),
        (200, end_click),
    ],
    "study-credit": [
        (1500, lambda lk: at_t0(lk, "credit-t0")),
        (200, open_click),
        (2000, lambda lk: studying(lk, "credit-open")),
        (200, credit_now),
    ],
}


def run_plan(name: str) -> None:
    """Run the real ``gate.main`` with the scripted lock; print EXIT=."""
    Scripted.plan = PLANS[name]
    gate_lock.EveningLock = Scripted
    started = time.monotonic()
    code = gate.main(["--production", "--evening"])
    say(f"EXIT={code} after {time.monotonic() - started:.1f}s")
    sys.exit(0)


def main(argv: list[str]) -> None:
    """Dispatch the sub-command."""
    if os.environ.get("DISPLAY", ":0") in {":0", ":0.0", ""}:
        fail("refusing to run on :0")
    command = argv[0]
    if command == "seed":
        seed(int(argv[1]), int(argv[2]))
    elif command == "probe":
        probe()
    else:
        run_plan(command)


if __name__ == "__main__":
    main(sys.argv[1:])
