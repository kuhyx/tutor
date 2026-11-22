#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Agent-E2E flows F23-F25: the guard's phase refuses gated teaching (C3, C4).

* F23 (``up --phase "theory $LC/prefix-sums"``): ``#/learn/LC/stack-queue``,
  a module outside ``teachable``, is refused (``no_card_left``) and the
  subject's plan shows; live session, transcripts, RTDB sessions and ledger
  are unchanged.
* F24 (``up --phase solve --unarchive SQL``: empty ``teachable``; kuhy has
  SQL archived, and a route into an archived subject stays on Home): every
  module of the plan carries ``teachable: false`` and every tile shows the
  lock glyph (spoken "Not teachable now"); then a learn route into the
  ungated SQL subject still starts a teaching session. The route names a
  STARTED SQL module: the module gate (F21) holds an unstarted one behind
  SQL's due reviews, in every phase. A model turn: ``send``, ``wait``,
  ``check``.
* F25 (``up``, no phase file): ``flow F25 missing``, then ``flow F25 bad``
  (it writes a ``theory`` row with a wrong ``hmac``). Each refuses a gated
  route twice (two reads of the file), and the server log has exactly one
  warning per failure, no Traceback, and ``/api/state`` still answers.
"""

from __future__ import annotations

import json
import time
from typing import Any, Final
import uuid

from e2e_flow import Flow, FlowError, State
from e2e_follow_up import COMPOSER, _ledger
from e2e_learn import learn
from e2e_learn_rows import transcripts
from e2e_phase import untaught, write
from e2e_takeover import LC, LOCK, MODULE, text_below

from tutor.curriculum.context import Context
from tutor.curriculum.fold import fold

SQL: Final = "mysql-8-for-timed-sql-coding-tests-joins-and"  # never gated
REFUSED: Final = "stack-queue"  # an LC module the theory row does not grant
F25_PHASES: Final = ("missing", "bad")
HTTP_OK: Final = 200
STATE_JS: Final = (
    "(() => { const x = new XMLHttpRequest();"
    " x.open('GET', '/api/state', false); x.send(); return x.status; })()"
)
WARNINGS: Final = {
    "missing": "nothing teachable: [Errno 2]",  # the unreadable-file warning
    "bad": "not a signed C3 row, nothing teachable",
}


def refused(flow: Flow, module: str) -> None:
    """``#/learn/LC/module`` is refused and lands on LC's plan."""
    before = flow.rids()
    learn(flow, LC, module)
    result = flow.result("session_start", before)
    if result.get("ok") or result.get("code") != "no_card_left":
        msg = f"want no_card_left, got {json.dumps(result)[:300]}"
        raise FlowError(msg)
    flow.step(f"the plan of {LC} shows, no session composer")
    if not text_below(flow.browser, LOCK, 30):
        msg = f"no plan; saw: {flow.browser.page_text()[:300]!r}"
        raise FlowError(msg)
    # The router does not mirror its screen in the URL: judge by the tiles.
    titles = [str(m["title"]) for m in plan_modules(flow)]
    text = flow.browser.page_text()
    shown = [t for t in titles if t in text]
    flow.note(f"{len(shown)} of {len(titles)} {LC} module titles on screen")
    if not shown or COMPOSER in text:
        msg = f"not on {LC}'s plan; saw: {text[:300]!r}"
        raise FlowError(msg)


def plan_modules(flow: Flow) -> list[dict[str, Any]]:
    """LC's published plan modules (with their ``teachable`` flags)."""
    return list(flow.db.node(f"subjects/{LC}/plan").get("modules") or [])


def f23(flow: Flow) -> None:
    """A refused module: the plan shows, nothing changes."""
    live, files = flow.db.node("live"), transcripts(flow)
    sessions, ledger = set(flow.db.node("sessions")), _ledger(flow.args.data)
    refused(flow, REFUSED)
    time.sleep(3)  # a late write would land now
    flow.step("live, transcripts, RTDB sessions and ledger are unchanged")
    after: list[tuple[str, Any, Any]] = [
        ("live", live, flow.db.node("live")),
        ("transcripts", files, transcripts(flow)),
        ("sessions", sessions, set(flow.db.node("sessions"))),
        ("ledger", ledger, _ledger(flow.args.data)),
    ]
    if changed := [name for name, was, now in after if was != now]:
        msg = f"changed: {changed}"
        raise FlowError(msg)


def _tiles_locked(flow: Flow, titles: list[str]) -> None:
    """Every module tile, scrolled through, carries the lock glyph."""
    flow.step(f"each of {len(titles)} tiles shows {LOCK!r}")
    seen: dict[str, str] = {}  # title -> the tile's status label after it
    flow.browser.scroll(-20000)  # from the top: tiles off screen drop out
    for _ in range(40):
        lines = flow.browser.page_text().splitlines()
        for i, line in enumerate(lines):
            if line in titles:  # the tile's status label follows its title
                seen[line] = lines[i + 1] if i + 1 < len(lines) else ""
        if len(seen) == len(titles):
            break
        flow.browser.scroll(500)
        time.sleep(0.5)
    first = next(iter(seen.items()), None)
    flow.note(f"tiles seen {len(seen)}/{len(titles)}; first: {first}")
    bad = sorted(t for t in titles if LOCK not in seen.get(t, ""))
    if bad:
        msg = f"tiles unseen or without the lock: {bad}"
        raise FlowError(msg)


def _into_view(flow: Flow, label: str) -> None:
    """Scroll until ``label`` is on screen (labels exist off screen too)."""
    for _ in range(10):
        hit = flow.browser.find(label)
        if hit is not None and hit["visible"]:
            break
        # Not built yet (None) means further down, like a hit below.
        flow.browser.scroll(-300 if hit is not None and not hit["below"] else 300)
        time.sleep(0.5)
    time.sleep(2)  # the tiles paint after the scroll settles


def _started_module(ctx: Context, cards: list[str]) -> str:
    """The module of the first of ``cards`` (untaught, SQL) the gate never holds.

    A module with a taught card: the module gate keeps an unstarted one shut
    until SQL's due reviews are done (24 on kuhy's data, more than one call).
    """
    recs = ctx.subjects.cards(SQL)
    taught = fold(ctx.log.read()).taught_ids(SQL)
    started = {recs[c].module for c in taught if c in recs}
    found = next((recs[c].module for c in cards if recs[c].module in started), None)
    if found is None:
        msg = f"{SQL} has no started module with an untaught card"
        raise FlowError(msg)
    return found


def f24_send(flow: Flow) -> State:
    """The locked plan; then a learn route into SQL."""
    flow.step(f"RTDB: every {LC} module is teachable: false")
    modules = plan_modules(flow)
    flags = {str(m.get("id")): m.get("teachable") for m in modules}
    flow.note(f"teachable flags: {flags}")
    if not modules or any(v is not False for v in flags.values()):
        msg = f"want every flag false: {flags}"
        raise FlowError(msg)
    flow.step(f"open #/plan/{LC}")
    flow.browser.open(f"{flow.args.app}?db={flow.args.db}#/plan/{LC}")
    if not text_below(flow.browser, LOCK, 30):  # the goal text sits above
        msg = f"no lock glyph; saw: {flow.browser.page_text()[:300]!r}"
        raise FlowError(msg)
    titles = [str(m["title"]) for m in modules]
    _tiles_locked(flow, titles)
    flow.browser.scroll(-20000)  # back to the top for the screenshot
    _into_view(flow, titles[0])
    flow.shot("plan_locked")
    ctx = Context(flow.args.data, device=str(uuid.uuid4()))
    cards = untaught(ctx, SQL)
    module = _started_module(ctx, cards)
    flow.note(f"{SQL}: {len(cards)} untaught; learn {module}")
    before = flow.rids()
    learn(flow, SQL, module)
    rid = flow.request("session_start", before)
    return {"rid": rid, "module": module, "cards": cards}


def f24_check(flow: Flow, state: State) -> None:
    """The SQL route started a teaching session on an untaught card of it."""
    flow.step("the SQL session_start result is ok")
    if not (result := flow.result_of(str(state["rid"]))).get("ok"):
        msg = f"SQL learn refused: {json.dumps(result)[:300]}"
        raise FlowError(msg)
    live = flow.db.node("live")
    flow.step(f"live is on an untaught {SQL}/{state['module']} card")
    flow.note(f"live={live}")
    if live.get("subject") != SQL or live.get("card") not in state["cards"]:
        msg = f"live={live}, want an untaught card of {SQL}"
        raise FlowError(msg)
    flow.screen("/session")
    flow.expect(COMPOSER, timeout=30)


def _server_log(flow: Flow) -> str:
    return (flow.args.data.parent / "server.log").read_text(encoding="utf-8")


def f25(flow: Flow) -> None:
    """One warning per phase-file failure; the server stays up and refuses."""
    phase = flow.args.phase
    path = flow.args.data.parent / "theory_phase.json"
    if phase == "bad":
        key = flow.args.data.parent / "test.key"
        flow.note(write(path, key, "bad", [f"{LC}/{MODULE}"]))
    elif path.exists():
        msg = f"{path} exists: run F25 missing on a fresh up"
        raise FlowError(msg)
    for _ in range(2):  # two reads of the same failure
        refused(flow, MODULE)
    flow.step("/api/state answers")
    # From the page (same origin as the server): a synchronous XHR's status.
    status = flow.browser.evaluate(STATE_JS)
    flow.note(f"/api/state: HTTP {status}")
    if status != HTTP_OK:
        msg = f"/api/state answered {status}"
        raise FlowError(msg)
    log = _server_log(flow)
    flow.step("the server log: one warning per failure, no Traceback")
    counts = {name: log.count(text) for name, text in WARNINGS.items()}
    flow.note(f"warnings {counts}, Tracebacks {log.count('Traceback')}")
    want = {"missing": 1, "bad": int(phase == "bad")}
    if counts != want or "Traceback" in log:
        msg = f"want warnings {want} and no Traceback, have {counts}"
        raise FlowError(msg)
