#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Agent-E2E flow F5: help on a struggling card (``DOCS-contract-struggle.md``).

Runs on a sandbox brought ``up --struggle``: ``e2e_seed.py struggle`` gave
the subject's first due card two Again ratings (``<sandbox>/f5_seed.json``),
so the Again tapped here is the third in a row and Review offers help (§4,
the offer shows right after the rating that makes 3, 6, ...).

* send: Home -> the subject tile's "Review (N due)" shows the seeded card
  first; Show answer,
  "1 Again"; "Struggling with this card?" is shown; "Get help" sends
  ``session_start`` with ``struggle: true``.
* check (after ``wait``: the opening turn is a real model turn, as F1's):
  the result is ok and the session is live on the card; its transcript's
  ``start`` event has ``struggle: true``; the system prompt the worker built
  (``e2e_server.py`` logs each one to ``<sandbox>/prompts.jsonl``) holds rule
  16 and "Again 3 times"; then a ``session_start`` ``struggle: true`` on an
  untaught card, put straight into the emulator, gets ``bad_request``.
"""

from __future__ import annotations

import json
from pathlib import Path
import time
import uuid

from e2e_flow import Flow, FlowError, State

from tutor.curriculum.ids import ulid

OFFER = "Struggling with this card?"
RULE_16 = ("16. STRUGGLING CARD", "# Struggling card", "rated Again 3 times")


def _seed(flow: Flow) -> dict[str, str]:
    """What ``up --struggle`` seeded (``{}`` on a sandbox without it)."""
    path = Path(flow.args.data).parent / "f5_seed.json"
    return json.loads(path.read_text()) if path.is_file() else {}


def f5_send(flow: Flow) -> State:
    """Review the subject, rate the struggling card Again, tap Get help."""
    seed = _seed(flow)
    flow.note(f"seed={seed or 'none (sandbox not up --struggle)'}")
    # The subject tile's Review on Home (the due queue reads the app's
    # catalog cache, which Home fills; a cold deep link sees no cards).
    flow.home()
    flow.tap(f"Review ({seed['due']} due)" if seed else "Review (", timeout=30)
    flow.step("the first card shown")
    if flow.browser.wait_for("Show answer (Space)", 30) is None:
        msg = f"no card to review; saw: {flow.browser.page_text()[:400]!r}"
        raise FlowError(msg)
    if seed and seed["front"] not in flow.browser.page_text():
        msg = f"PRECONDITION: {seed['card']} is not first; saw: "
        raise FlowError(msg + repr(flow.browser.page_text()[:400]))
    flow.tap("Show answer (Space)")
    flow.tap("1 Again")
    flow.step(f'"{OFFER}" is shown')
    if flow.browser.wait_for(OFFER, 15) is None:
        msg = f"no help offer; saw: {flow.browser.page_text()[:400]!r}"
        raise FlowError(msg)
    flow.shot("offer")
    before = flow.rids()
    flow.tap("Get help")
    rid = flow.request("session_start", before)
    body = flow.db.node(f"requests/{rid}/req").get("body") or {}
    flow.note(f"body={body}")
    if body.get("struggle") is not True or body.get("card") != seed.get("card"):
        msg = f"session_start body {body}, want struggle on {seed.get('card')}"
        raise FlowError(msg)
    return {"rid": rid, "seed": seed}


def _transcript_start(flow: Flow, sid: str) -> dict[str, object]:
    path = Path(flow.args.data) / "sessions" / f"{sid}.jsonl"
    first: dict[str, object] = json.loads(path.read_text().splitlines()[0])
    return first


def _prompt_has_rule_16(flow: Flow) -> None:
    flow.step("the session's system prompt holds rule 16")
    path = Path(flow.args.data).parent / "prompts.jsonl"
    lines = path.read_text().splitlines() if path.is_file() else []
    if not lines:
        msg = f"no system prompt logged in {path}"
        raise FlowError(msg)
    prompt = str(json.loads(lines[-1])["prompt"])
    if missing := [m for m in RULE_16 if m not in prompt]:
        msg = f"the newest prompt lacks {missing}"
        raise FlowError(msg)
    flow.note(f"prompt {len(prompt)} chars: {', '.join(RULE_16)}")


def _untaught_refused(flow: Flow, seed: dict[str, str]) -> None:
    flow.step(f"struggle on untaught {seed['untaught']} -> bad_request")
    now = int(time.time() * 1000)
    rid = ulid(now)
    flow.db.put(
        f"requests/{rid}/req",
        {
            "kind": "session_start",
            "dev": str(uuid.uuid4()),
            "created": now,
            "body": {
                "subject": seed["subject"],
                "card": seed["untaught"],
                "struggle": True,
                "device": "desktop",
            },
        },
    )
    deadline = time.monotonic() + 20
    while not (result := flow.result_of(rid)) and time.monotonic() < deadline:
        time.sleep(0.5)
    flow.note(f"result={json.dumps(result)[:300]}")
    if result.get("code") != "bad_request":
        msg = f"want bad_request, got {json.dumps(result)[:300]}"
        raise FlowError(msg)


def f5_check(flow: Flow, state: State) -> None:
    """A struggle session on the card, with rule 16; untaught is refused."""
    seed = dict(state["seed"])
    flow.step("the session_start result is ok, live on the card")
    result = flow.result_of(str(state["rid"]))
    flow.note(f"result={json.dumps(result)[:300]}")
    live = flow.db.node("live")
    if not result.get("ok") or live.get("card") != seed["card"]:
        msg = f"result={result} live={live}, want {seed['card']}"
        raise FlowError(msg)
    flow.step("the transcript's start event has struggle: true")
    start = _transcript_start(flow, str(live["session"]))
    flow.note(f"start={start}")
    if start.get("struggle") is not True or start.get("card") != seed["card"]:
        msg = f"start event {start}"
        raise FlowError(msg)
    _prompt_has_rule_16(flow)
    flow.screen("/session")
    flow.expect("Send", timeout=30)
    flow.shot("session")
    _untaught_refused(flow, seed)
