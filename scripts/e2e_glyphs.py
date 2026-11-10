#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Agent-E2E F16: every server code, blocked state, pause and phase as a glyph.

The cases the real worker rarely or never produces on demand (todo
340c295b-11: C2, C4, C6, C11). ``scripts/e2e_sandbox.sh hold`` first swaps
the sandbox server for a static host of the same web build, so no worker
claims anything: this flow plays the worker, writing ``claim`` and
``result`` nodes into the emulator for the requests the real app sends.
Each phase taps Start session, answers the new ``session_start`` and
screenshots the cue (``<out>_<phase>_<case>.png``); the agent Reads the
frames to compare glyphs. One phase per call (each under 60 s):

* ``codes`` / ``codes2``: the ten non-blocking codes, then an unknown one.
* ``nocard``: ``no_card_left`` due later (countdown), due now, a module to
  review, nothing open.
* ``phases``: claimed, thinking, images, checking_images, publishing, then
  an unknown phase.
* ``pauses``: the session header with a low-effort and a stalled pause.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from e2e_flow import FlowError

if TYPE_CHECKING:
    from e2e_flow import Flow

CODES = (
    "model_error",
    "worker_error",
    "bad_request",
    "not_live",
    "session_live",
    "plan_conflict",
)
CODES2 = ("edit_refused", "focus_refused", "unknown_prompt", "gave_up", "zz_new_code")
# The app's spoken sentence for each (app/lib/relay/error_text.dart).
SPOKEN = {
    "model_error": "The tutor model failed on this turn.",
    "worker_error": "Something broke on the PC.",
    "bad_request": "The PC could not read that request.",
    "not_live": "That session is no longer live.",
    "session_live": "Another session is live.",
    "plan_conflict": "The plan changed meanwhile.",
    "edit_refused": "The card edit was refused.",
    "focus_refused": "The focus project was refused.",
    "unknown_prompt": "The request failed (unknown_prompt).",
    "gave_up": "The PC gave up after three attempts.",
    "zz_new_code": "The request failed (zz_new_code).",
}
PHASE_SPOKEN = (
    ("claimed", "The PC picked it up..."),
    ("thinking", "Tutor is thinking..."),
    ("images", "Finding pictures..."),
    ("checking_images", "Checking the pictures..."),
    ("publishing", "Publishing the reply..."),
    ("zz_new_phase", "The PC is working on it..."),
)
# (frame, paused_reason, awaiting the reply this long ago in ms, spoken).
PAUSES = (
    ("low_effort", "low-effort reply", None, "Clock paused"),
    ("stalled", "no reply for 10 min", None, "Clock paused"),
    ("stalled_pill", "no reply for 10 min", 3_600_000, "Stalled"),
)
PHASES = ("codes", "codes2", "nocard", "phases", "pauses")


def _now_ms() -> int:
    return int(time.time() * 1000)


def _start(flow: Flow) -> str:
    """No live session; open Session, tap Start; the new ``session_start`` rid."""
    flow.db.put("live", None)
    flow.screen("/session")
    before = flow.rids()
    flow.tap("Start session", timeout=30)
    return flow.request("session_start", before)


def _answer(flow: Flow, rid: str, result: dict[str, Any]) -> None:
    flow.step(f"answer {rid} with {result}")
    node = {"ok": False, "retry": False, "at": _now_ms(), **result}
    flow.db.put(f"requests/{rid}/result", node)


def _see(flow: Flow, spoken: str, suffix: str) -> None:
    flow.expect(spoken)
    time.sleep(1)  # the glyph is painted
    flow.shot(suffix)


def _codes(flow: Flow, codes: tuple[str, ...]) -> None:
    for code in codes:
        rid = _start(flow)
        _answer(flow, rid, {"code": code, "error": f"worker text for {code}"})
        _see(flow, SPOKEN[code], f"code_{code}")
        if f"worker text for {code}" in flow.browser.page_text():
            msg = f"the worker's error is on the page for {code}"
            raise FlowError(msg)


def _nocard(flow: Flow) -> None:
    hour = 3600 * 1000
    cases = (
        ("due_later", {"next": "reviews_due", "due_at": _now_ms() + 5 * hour}),
        ("due_now", {"next": "reviews_due", "due_at": _now_ms() - 60_000}),
        ("module", {"next": "review_module", "module": "m1", "module_title": "M"}),
        ("none", {}),
    )
    for name, extra in cases:
        rid = _start(flow)
        result = {"code": "no_card_left", "error": "x", "subject": flow.args.subject}
        _answer(flow, rid, {**result, **extra})
        _see(flow, "No card left to teach", f"nocard_{name}")


def _phases(flow: Flow) -> None:
    rid = _start(flow)
    for phase, spoken in PHASE_SPOKEN:
        claim = {
            "by": "e2e",
            "lease_until": _now_ms() + 600_000,
            "attempt": 1,
            "phase": phase,
            "at": _now_ms(),
        }
        flow.step(f"claim {rid} in phase {phase}")
        flow.db.put(f"requests/{rid}/claim", claim)
        _see(flow, spoken, f"phase_{phase}")
    _answer(flow, rid, {"code": "worker_error", "error": "x"})
    _see(flow, SPOKEN["worker_error"], "phase_done")
    flow.expect("Start session")  # the screen kept working


def _pauses(flow: Flow) -> None:
    sid = flow.args.session
    meta = flow.db.node(f"sessions/{sid}/meta")
    if not meta:
        msg = f"session {sid} has no meta in the emulator"
        raise FlowError(msg)
    card = (meta.get("card") or {}).get("id")
    live = {"session": sid, "card": card, "subject": meta.get("subject")}
    for name, reason, ago, spoken in PAUSES:
        clock = dict(meta.get("clock") or {})
        clock["paused_reason"] = reason
        clock.pop("awaiting_since", None)
        if ago is not None:
            clock["awaiting_since"] = _now_ms() - ago
        flow.step(f"session {sid} paused: {reason}, awaiting {ago}")
        flow.db.put(f"sessions/{sid}/meta", {**meta, "stopped": False, "clock": clock})
        flow.db.put("live", live)
        flow.screen("/session")
        flow.expect(spoken, timeout=25)
        time.sleep(1.5)
        flow.shot(f"pause_{name}")


def f16(flow: Flow) -> None:
    """Run the phase named by ``flow.args.phase`` (module doc)."""
    match flow.args.phase:
        case "codes":
            _codes(flow, CODES)
        case "codes2":
            _codes(flow, CODES2)
        case "nocard":
            _nocard(flow)
        case "phases":
            _phases(flow)
        case "pauses":
            _pauses(flow)
        case other:
            msg = f"F16 phase {other!r} is not one of {', '.join(PHASES)}"
            raise FlowError(msg)
