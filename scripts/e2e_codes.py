#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Agent-E2E F13: the machine codes beside a failure reach the app (§4a).

One call, no model turn: for each outage reason an ``unavailable.jsonl``
window is written into the sandbox data dir, so the worker refuses the
next ``session_start`` at once (``outage.ensure_available``). The flow
taps "Continue learning", asserts the result node carries ``code``,
``reason`` and ``error_kind``, waits for the auto-switched drill's banner
and screenshots it (``<out>_<reason>.png``): each reason's glyph must
differ, which an agent checks by reading the frames. The window is removed
afterwards. Run by ``scripts/e2e_sandbox.sh flow F13 <reason>`` (one reason
per call, each under 60 s) on a fresh ``up``.
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING

from e2e_flow import FlowError

if TYPE_CHECKING:
    from pathlib import Path

    from e2e_flow import Flow

# Outage reason -> the error_kind the worker must send beside it.
REASONS = (
    ("rate_limit", "claude_limit"),
    ("overloaded", "claude_overloaded"),
    ("network", "claude_network"),
)
OUTAGES = tuple(reason for reason, _ in REASONS)


def _window(data: Path, reason: str) -> None:
    now = int(time.time())
    line = {"start": now - 5, "end": now + 3600, "reason": reason}
    (data / "unavailable.jsonl").write_text(json.dumps(line) + "\n", encoding="utf-8")


def f13(flow: Flow) -> None:
    """Each outage reason: its codes on the wire, its glyph on the banner."""
    data = flow.args.data
    picked = [(r, k) for r, k in REASONS if flow.args.phase in {r, "all"}]
    try:
        for reason, kind in picked:
            flow.step(f"Claude unavailable ({reason}) in the sandbox")
            _window(data, reason)
            flow.home()
            before = flow.rids()
            flow.tap("Continue learning", timeout=30)
            got = flow.start_result(before)
            want = {"code": "claude_unavailable", "reason": reason, "error_kind": kind}
            seen = {k: got.get(k) for k in want}
            flow.note(f"codes={seen}")
            if seen != want:
                msg = f"want {want}, got {json.dumps(got)[:300]}"
                raise FlowError(msg)
            flow.step("the drill opens with the Claude-out banner")
            if flow.browser.wait_for("Claude limit", 20) is None:
                msg = f"no banner; saw: {flow.browser.page_text()[:400]!r}"
                raise FlowError(msg)
            time.sleep(1)  # the banner's glyph is painted
            flow.shot(reason)
    finally:
        (data / "unavailable.jsonl").unlink(missing_ok=True)
