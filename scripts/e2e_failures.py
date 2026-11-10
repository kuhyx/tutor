#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Agent-E2E F14: real failures reach the app with their machine codes (§4a).

Each phase is one call (< 60 s) and drives the real app against the real
worker; nothing is written into the emulator that a second device could not
send. ``phase`` picks the case:

* ``drill`` (C2, C9): the app shows a drill question; a second device asks
  for the next one, so the app's answer is refused ``unknown_prompt``. The
  failure cue appears and Retry sends the answer again.
* ``coach`` (C3): the coach opens a slug with no public statement; the
  worker refuses ``bad_request`` with ``reason: paste_statement`` and the
  app opens the paste box.
* ``subject`` (C7): Home -> "I want to learn..." -> Draft a plan, on a
  sandbox whose Claude calls fail (``up --model-down network|refuse``): the
  subject's meta turns ``failed`` with ``error_kind`` claude_network or
  model_failed, and its tile shows the failure.
* ``module`` (C8): a second device pregenerates a locked module of an
  approved subject; with Claude failing it turns ``failed`` with its
  ``error_kind``. ``module-retry``: after ``restart --model-down <other>``,
  the app's Retry on that module fails it again with the other kind.

The expected kind follows the sandbox's ``MODEL`` (``network`` ->
claude_network, ``refuse`` -> model_failed). Screenshots are
``<out>_<phase>.png``; an agent reads them for the glyphs.
"""

from __future__ import annotations

import json
from pathlib import Path
import time
from typing import TYPE_CHECKING, Any
import uuid

from e2e_flow import FlowError

from tutor.curriculum.ids import ulid

if TYPE_CHECKING:
    from e2e_flow import Flow

PHASES = ("drill", "coach", "subject", "module", "module-retry")
_KIND = {"network": "claude_network", "refuse": "model_failed"}
_GOAL = "I want to learn how tides work e2e "


def _model(flow: Flow) -> str:
    state = Path(flow.args.state).parent / "state"
    for line in state.read_text().splitlines():
        if line.startswith("MODEL="):
            return line.removeprefix("MODEL=")
    return ""


def _send(flow: Flow, kind: str, body: dict[str, Any]) -> str:
    """PUT a request as a second device would; returns its rid."""
    now = int(time.time() * 1000)
    rid = ulid(now)
    req = {"kind": kind, "dev": str(uuid.uuid4()), "created": now, "body": body}
    flow.db.put(f"requests/{rid}/req", req)
    return rid


def _await(flow: Flow, rid: str, seconds: float = 30) -> dict[str, Any]:
    deadline = time.monotonic() + seconds
    while not (result := flow.result_of(rid)) and time.monotonic() < deadline:
        time.sleep(0.5)
    flow.note(f"result={json.dumps(result)[:300]}")
    if not result:
        msg = f"no result for {rid} in {seconds:.0f} s"
        raise FlowError(msg)
    return result


def _drill(flow: Flow) -> None:
    flow.screen("/drill")
    before = flow.rids()
    shown = flow.result("drill_next", set(), timeout=30)
    options = [str(o) for o in (shown.get("data") or {}).get("options") or []]
    if not options:
        msg = f"no drill question: {json.dumps(shown)[:300]}"
        raise FlowError(msg)
    time.sleep(2)
    flow.step("a second device takes the next question")
    _await(flow, _send(flow, "drill_next", {"subject": None}))
    flow.tap(options[0][:40])
    got = flow.result("drill_answer", before)
    if got.get("code") != "unknown_prompt":
        msg = f"want unknown_prompt, got {json.dumps(got)[:300]}"
        raise FlowError(msg)
    flow.expect("Retry")
    flow.shot("drill")
    answered = flow.rids()
    flow.tap("Retry")
    flow.result("drill_answer", answered)  # Retry resent the answer
    flow.note("Retry sent the answer again")


def _coach(flow: Flow) -> None:
    flow.screen("/coach")
    before = flow.rids()
    flow.type_into("LeetCode problem", f"zz-e2e-no-such-problem-{uuid.uuid4().hex[:6]}")
    flow.tap("Start")
    got = flow.result("lc_open", before, timeout=40)
    want = {"code": "bad_request", "reason": "paste_statement"}
    if {k: got.get(k) for k in want} != want:
        msg = f"want {want}, got {json.dumps(got)[:300]}"
        raise FlowError(msg)
    flow.expect("Statement")  # the paste box
    flow.shot("coach")


def _subject(flow: Flow, kind: str) -> None:
    flow.home()
    before = flow.rids()
    flow.type_into("I want to learn...", _GOAL + _model(flow))
    flow.tap("Draft a plan")
    got = flow.result("subject_new", before, timeout=45)
    if got.get("error_kind") != kind:
        msg = f"want error_kind {kind}, got {json.dumps(got)[:300]}"
        raise FlowError(msg)
    flow.step("the subject's meta is failed with its error_kind")
    metas = flow.db.node("subjects")
    failed = {
        sid: node.get("meta") or {}
        for sid, node in metas.items()
        if (node.get("meta") or {}).get("goal", "").startswith(_GOAL.strip())
    }
    flow.note(f"metas={json.dumps(failed)[:300]}")
    if not any(m.get("error_kind") == kind for m in failed.values()):
        msg = f"no failed meta with error_kind {kind}"
        raise FlowError(msg)
    flow.home()
    time.sleep(4)
    flow.browser.wait_for("failed", 15)
    flow.shot(f"subject_{kind}")


def _approved_locked(flow: Flow) -> tuple[str, str]:
    for sid, node in sorted(flow.db.node("subjects").items()):
        plan = node.get("plan") or {}
        if plan.get("status") != "approved":
            continue
        for module in plan.get("modules") or []:
            if module.get("status") == "locked" and not module.get("pregenerated"):
                return sid, str(module["id"])
    msg = "no approved subject with a locked module"
    raise FlowError(msg)


def _module_state(flow: Flow, sid: str, mid: str) -> dict[str, Any]:
    plan = flow.db.node(f"subjects/{sid}/plan")
    return next((m for m in plan.get("modules") or [] if m.get("id") == mid), {})


def _wait_failed(flow: Flow, sid: str, mid: str, kind: str) -> None:
    flow.step(f"{sid}/{mid} fails with error_kind {kind}")
    deadline = time.monotonic() + 40
    module: dict[str, Any] = {}
    while time.monotonic() < deadline:
        module = _module_state(flow, sid, mid)
        if module.get("status") == "failed" and module.get("error_kind") == kind:
            flow.note(f"module={json.dumps(module)[:300]}")
            return
        time.sleep(1)
    msg = f"module not failed/{kind}: {json.dumps(module)[:300]}"
    raise FlowError(msg)


def _module(flow: Flow, kind: str) -> None:
    sid, mid = _approved_locked(flow)
    seed = Path(flow.args.state).with_suffix(".module.json")
    seed.write_text(json.dumps({"subject": sid, "module": mid}))
    flow.step(f"a second device pregenerates {sid}/{mid}")
    _await(flow, _send(flow, "module_pregenerate", {"subject": sid, "modules": [mid]}))
    _wait_failed(flow, sid, mid, kind)
    flow.screen(f"/plan/{sid}")
    time.sleep(5)
    flow.shot(f"module_{kind}")


def _module_retry(flow: Flow, kind: str) -> None:
    seed = json.loads(Path(flow.args.state).with_suffix(".module.json").read_text())
    sid, mid = seed["subject"], seed["module"]
    flow.screen(f"/plan/{sid}")
    time.sleep(4)
    flow.tap("Retry", timeout=25)
    _wait_failed(flow, sid, mid, kind)
    time.sleep(3)
    flow.shot(f"module_{kind}")


def f14(flow: Flow) -> None:
    """Run the phase named by ``flow.args.phase`` (module doc)."""
    phase = flow.args.phase
    kind = _KIND.get(_model(flow), "")
    if phase in {"subject", "module", "module-retry"} and not kind:
        msg = f"F14 {phase} needs up/restart --model-down network|refuse"
        raise FlowError(msg)
    match phase:
        case "drill":
            _drill(flow)
        case "coach":
            _coach(flow)
        case "subject":
            _subject(flow, kind)
        case "module":
            _module(flow, kind)
        case "module-retry":
            _module_retry(flow, kind)
        case _:
            msg = f"F14 phase is one of {', '.join(PHASES)}"
            raise FlowError(msg)
