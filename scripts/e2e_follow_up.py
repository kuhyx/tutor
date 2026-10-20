#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Agent-E2E flows F3 and F4: follow-up questions (``tutor/follow_up.py``).

Both run on a sandbox whose ``--session`` (default the session kuhy asked
about, 20261020-172115-3f84) stopped at card end: ``up --as-of`` a moment
after its card_done turn and before its Next card, so the worker resumes it
live at card end.

* F3 card end: "Continue session" shows Next card, Stop here and the
  composer; a follow-up gets a tutor reply, the card stays done, Next card /
  Stop here stay, the events are tagged, and the sandbox ledger's rows for
  the session are unique and never overlap (new minutes continue its
  ``-m<n>`` numbering), and the reply's turn has a trace (stored and
  published) whose Thinking panel is on screen. Run it twice a minute apart
  to see a new row.
* F4 History: the live session is stopped (Stop here), then History ->
  that session -> "Ask a follow-up" reopens it and the tutor answers.

Each flow is a send step (``*_send``: taps up to the request, returns the
state) and a check step (``*_check``); ``e2e_drive.py`` waits in between.
"""

from __future__ import annotations

import itertools
import json
from typing import TYPE_CHECKING, Any

from e2e_flow import Flow, FlowError, State

if TYPE_CHECKING:
    from pathlib import Path

ASK_F3 = (
    "What if I just write the name down in a certificate myself and act as "
    "the certificate's owner?"
)
ASK_F4 = "In one sentence: who checks the signature on that certificate?"
COMPOSER = "Your answer"  # the composer box's label (prefix)


def _events(data: Path, sid: str) -> list[dict[str, Any]]:
    path = data / "sessions" / f"{sid}.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _ledger(data: Path) -> list[dict[str, Any]]:
    path = data / "ledger.json"
    if not path.is_file():
        return []
    rows = json.loads(path.read_text()).get("entries", [])
    return [r for r in rows if isinstance(r, dict) and r.get("kind") == "credit"]


def _minutes(rows: list[dict[str, Any]], sid: str) -> list[tuple[int, int]]:
    """The (first, last) minute each of ``sid``'s rows pays."""
    spans = []
    for row in rows:
        own, _, last = str(row["entry_id"]).rpartition("-m")
        if own == sid:
            paid = int((row.get("detail") or {}).get("minutes", 15))
            spans.append((int(last) - paid + 1, int(last)))
    return sorted(spans)


def _credit(flow: Flow, sid: str, before: list[dict[str, Any]]) -> None:
    """Rows unique and disjoint; new minutes come after the old ones."""
    flow.step("sandbox ledger: no id collision, minutes continue")
    after = _ledger(flow.args.data)
    ids = [r["entry_id"] for r in after]
    if len(ids) != len(set(ids)):
        msg = f"duplicate entry ids: {sorted(ids)}"
        raise FlowError(msg)
    old, now = _minutes(before, sid), _minutes(after, sid)
    new = [s for s in now if s not in old]
    for (_, end), (start, _) in itertools.pairwise(now):
        if start <= end:
            msg = f"overlapping minutes in {now}"
            raise FlowError(msg)
    if new and old and new[0][0] <= old[-1][1]:
        msg = f"new rows {new} do not continue after {old}"
        raise FlowError(msg)
    refused = [
        e.get("error")
        for e in _events(flow.args.data, sid)
        if e.get("type") == "credit" and e.get("error")
    ]
    if any("already present" in str(err) for err in refused):
        msg = f"a credit hit an existing entry id: {refused}"
        raise FlowError(msg)
    clock = flow.db.node(f"sessions/{sid}/meta").get("clock") or {}
    print(f"  rows before {old}; new rows {new or 'none this run'}")
    print(f"  active_seconds={clock.get('active_seconds')}")


def _replied(flow: Flow, sid: str, count: int) -> None:
    """A tutor message after the first ``count`` messages, card still done."""
    flow.step("a new tutor message; the card is still done")
    msgs = [m for _, m in sorted(flow.db.node(f"sessions/{sid}/msgs").items())]
    tutor = [m for m in msgs[count:] if m.get("role") == "tutor"]
    if not tutor:
        msg = f"no tutor reply after message {count}"
        raise FlowError(msg)
    print(f"  tutor: {str(tutor[-1].get('text', '')).strip()[:200]!r}")
    meta = flow.db.node(f"sessions/{sid}/meta")
    if not meta.get("card_done") or meta.get("stopped"):
        msg = f"meta after the follow-up: {meta}"
        raise FlowError(msg)


def _tagged(flow: Flow, sid: str, *kinds: str) -> None:
    """The newest events of ``kinds`` carry ``follow_up: true``."""
    flow.step("the transcript tags the follow-up events")
    events = _events(flow.args.data, sid)
    for kind in kinds:
        last = next(e for e in reversed(events) if e.get("type") == kind)
        if last.get("follow_up") is not True:
            msg = f"last {kind} event is not tagged: {str(last)[:300]}"
            raise FlowError(msg)


def _ask(flow: Flow, sid: str, text: str) -> State:
    """Type ``text`` in the composer and Send; the state to check the reply."""
    count = len(flow.db.node(f"sessions/{sid}/msgs"))
    since = flow.rids()
    flow.type_into(COMPOSER, text)
    flow.tap("Send")
    return {"sid": sid, "count": count, "rid": flow.request("message", since)}


def _answered(flow: Flow, state: State) -> str:
    """The message request succeeded and the tutor replied; the session id."""
    sid = str(state["sid"])
    flow.step("the follow-up's message result is ok")
    if not (result := flow.result_of(str(state["rid"]))).get("ok"):
        msg = f"follow-up refused: {json.dumps(result)[:300]}"
        raise FlowError(msg)
    _replied(flow, sid, int(state["count"]))
    return sid


def _traced(flow: Flow, sid: str) -> None:
    """The reply's turn has a trace, stored and published, and its panel shows."""
    flow.step("the reply's turn carries a trace (transcript + emulator)")
    events = _events(flow.args.data, sid)
    tutor = next(e for e in reversed(events) if e["type"] == "tutor")
    steps = (tutor.get("ui") or {}).get("trace") or []
    msgs = [m for _, m in sorted(flow.db.node(f"sessions/{sid}/msgs").items())]
    published = next(m for m in reversed(msgs) if m.get("role") == "tutor").get("trace")
    kinds = [s.get("kind") for s in steps]
    print(f"  trace: {len(steps)} steps {kinds[:12]}; published {len(published or [])}")
    if not steps or not published:
        msg = f"no trace on the reply (transcript {len(steps)}, msgs {published!r})"
        raise FlowError(msg)
    # The folded panel's header merges into the reply bubble's label
    # ("Tutor\n<text>\nThinking ..."); no earlier turn of this session has one.
    flow.step("the Thinking panel is on screen")
    lines = flow.browser.page_text().splitlines()
    if not any(line.startswith("Thinking") for line in lines):
        msg = f"no Thinking panel; saw: {flow.browser.page_text()[-400:]!r}"
        raise FlowError(msg)


def f3_send(flow: Flow) -> State:
    """Card end: Continue session, then ask a follow-up."""
    sid = flow.args.session
    flow.step(f"precondition: {sid} is live at card end")
    meta = flow.db.node(f"sessions/{sid}/meta")
    if flow.db.node("live").get("session") != sid or not meta.get("card_done"):
        msg = f"live={flow.db.node('live')} card_done={meta.get('card_done')}"
        raise FlowError(msg)
    before = _ledger(flow.args.data)
    flow.home()
    flow.tap("Continue session", timeout=30)
    flow.expect("Next card", "Stop here", "Send")
    flow.shot("card_end")
    return _ask(flow, sid, ASK_F3) | {"ledger": before}


def f3_check(flow: Flow, state: State) -> None:
    """The follow-up is answered with a trace; Next card / Stop here stay."""
    sid = _answered(flow, state)
    _tagged(flow, sid, "learner", "tutor")
    _credit(flow, sid, state["ledger"])
    flow.screen("/session")
    flow.expect("Next card", "Stop here", "Send", timeout=30)
    _traced(flow, sid)
    flow.shot("reply")


def f4_send(flow: Flow) -> State:
    """Stop here, then History -> the session -> Ask a follow-up."""
    sid = flow.args.session
    if flow.db.node("live").get("session") == sid:
        flow.screen("/session")
        flow.expect("Next card", timeout=30)  # card end drawn: its Stop here
        since = flow.rids()
        flow.tap("Stop here", timeout=30)
        if not flow.result("stop", since).get("ok"):
            msg = "Stop here failed"
            raise FlowError(msg)
    flow.step(f"precondition: {sid} is stopped")
    if not flow.db.node(f"sessions/{sid}/meta").get("stopped"):
        msg = f"{sid} is not stopped"
        raise FlowError(msg)
    count = len(flow.db.node(f"sessions/{sid}/msgs"))
    before = _ledger(flow.args.data)
    flow.screen("/history")
    flow.tap(f"{sid[:4]}-{sid[4:6]}-{sid[6:8]} {sid[9:11]}:{sid[11:13]}", timeout=30)
    flow.expect("Ask a follow-up")
    since = flow.rids()
    flow.type_into("Ask a follow-up", ASK_F4)
    flow.shot("history")
    flow.tap("Ask")
    if not (result := flow.result("follow_up_open", since)).get("ok"):
        msg = f"follow_up_open refused: {json.dumps(result)[:300]}"
        raise FlowError(msg)
    rid = flow.request("message", since)
    return {"sid": sid, "count": count, "rid": rid, "ledger": before}


def f4_check(flow: Flow, state: State) -> None:
    """The reopened session is live and the tutor answered the follow-up."""
    sid = _answered(flow, state)
    if flow.db.node("live").get("session") != sid:
        msg = f"live={flow.db.node('live')}, want {sid}"
        raise FlowError(msg)
    if not any(e["type"] == "follow_up_open" for e in _events(flow.args.data, sid)):
        msg = "no follow_up_open event in the transcript"
        raise FlowError(msg)
    _tagged(flow, sid, "learner", "tutor")
    _credit(flow, sid, state["ledger"])
    flow.screen("/session")
    flow.expect("Next card", "Stop here", "Send", timeout=30)
    flow.shot("answered")
