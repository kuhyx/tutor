#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""F33's Start phases (``e2e_fallback.py``): due, read, paid, drill, empty, ...

Each one is one call on a sandbox ``up --outage R --fallback B`` (module
doc of ``e2e_fallback.py``), screenshots its key frame as ``f33_<phase>``
and fails with the step that saw something else.
"""

from __future__ import annotations

import json
from pathlib import Path
import time
from typing import TYPE_CHECKING, Any, Final

from e2e_fallback_checks import (
    left_count,
    log_events,
    read_problems,
    read_rows,
    run_active,
)
from e2e_fallback_steps import (
    FLIP,
    RATE,
    dwell,
    fit_check,
    flip,
    home_start,
    new_nodes,
    no_error,
    no_session_start,
    rate,
    shown_card,
)
from e2e_flow import FlowError

from tutor.curriculum.context import Context

if TYPE_CHECKING:
    from e2e_flow import Flow

READ_DWELL: Final = 15.0  # per card in `read`: two of them fit one call
PAID_AT: Final = 63.0  # active seconds of the run once `paid` rates its card
EMPTY: Final = "Nothing left to read"
REVEAL: Final = "Show answer (Space)"  # the Review card's flip


def due(flow: Flow) -> None:
    """C3: Start opens the Review on a due card; no chat request, no error."""
    seeded = json.loads((Path(flow.args.data).parent / "f33_seed.json").read_text())
    before = home_start(flow)
    flow.expect(REVEAL, timeout=20)
    flow.step(f"the Review shows the {len(seeded['due'])} seeded due cards")
    deadline = time.monotonic() + 15
    while (left := left_count(flow.browser.page_text())) is None:
        if time.monotonic() > deadline:
            msg = f"no 'N left'; saw: {flow.browser.page_text()[:400]!r}"
            raise FlowError(msg)
        time.sleep(0.5)
    flow.note(f"{left} left")
    if left != len(seeded["due"]):
        msg = f"the Review has {left} cards, want {len(seeded['due'])}"
        raise FlowError(msg)
    no_session_start(flow, before)
    no_error(flow)
    flow.shot("due")


def read(flow: Flow) -> None:
    """C4, C5: front, flip, back; Got it on one card, Again on the next."""
    since_ms, counts = int(time.time() * 1000), taught(Path(flow.args.data))
    before = home_start(flow)
    first = shown_card(flow, before, set())
    flow.shot("read_front")
    flip(flow)
    flow.shot("read")
    if not str(first.get("excerpt") or "").strip():
        msg = f"card {first['id']} has no excerpt to show"
        raise FlowError(msg)
    dwell(flow, READ_DWELL)
    rated = [rate(flow, "Got it")]
    second = shown_card(flow, before, {first["id"]})
    flip(flow)
    dwell(flow, READ_DWELL)
    rated.append(rate(flow, "Again"))
    shown_card(flow, before, {first["id"], second["id"]})
    flow.shot("read_next")
    no_session_start(flow, before)
    flow.step("the log has taught + unchecked for both, a review rated 1 for Again")
    refs = [(c["subject"], c["id"]) for c in (first, second)]
    if problems := read_problems(
        log_events(flow.args.data), refs[0], refs[1], since_ms
    ):
        raise FlowError("; ".join(problems))
    flow.step(f"{first['subject']}'s taught count rose by 2")
    after = taught(Path(flow.args.data))
    gain = sum(after.get(s, 0) - counts.get(s, 0) for s in {r[0] for r in refs})
    flow.note(f"taught {counts.get(refs[0][0])} -> {after.get(refs[0][0])}")
    if gain != len(refs):
        msg = f"taught count rose by {gain}, want {len(refs)}"
        raise FlowError(msg)
    due_at = again_due(flow, refs[1])
    active = run_active(Path(flow.args.data))
    flow.note(f"read run active so far: {active:.1f} s; results {rated}")
    today = flow.db.node("stats").get("today") or {}
    state = {
        "cards": refs,
        "since": since_ms / 1000,
        "active": active,
        "today": today,
        "again_due": due_at,
    }
    Path(flow.args.state).write_text(json.dumps(state), encoding="utf-8")


def again_due(flow: Flow, ref: tuple[str, str]) -> dict[str, Any]:
    """When the "again" card falls due (the fold's FSRS state); recorded, not judged.

    C5 asks for "within the day"; ``read_mode.py`` schedules Again as "due
    in a day": the note says which local day it lands on.
    """
    flow.step(f"when {ref[1]} falls due")
    state = Context(Path(flow.args.data), device="e2e").fold().card(*ref).fsrs_state()
    if state is None:
        msg = f"{ref} has no FSRS state after Again"
        raise FlowError(msg)
    now, due = time.time(), state["due"] / 1000
    out = {
        "hours": round((due - now) / 3600, 2),
        "same_day": time.localtime(due)[:3] == time.localtime(now)[:3],
    }
    flow.note(f"due in {out['hours']} h; same local day: {out['same_day']}")
    return out


def taught(data: Path) -> dict[str, int]:
    """Taught cards per subject, by the server's fold (Home's tile count)."""
    ctx = Context(data, device="e2e")
    folded = ctx.fold()
    return {s: len(folded.taught_ids(s)) for s in ctx.subjects.subjects()}


def paid(flow: Flow) -> None:
    """C5: one more card past a minute of reading pays a ``read-`` ledger row."""
    state = json.loads(Path(flow.args.state).read_text(encoding="utf-8"))
    before = home_start(flow)
    card = shown_card(flow, before, set())
    flip(flow)
    dwell(flow, PAID_AT - float(state["active"]))
    result = rate(flow, "Got it")
    flow.step("the rating credited a minute; the ledger has a read- row")
    rows = read_rows(Path(flow.args.data), float(state["since"]))
    flow.note(f"result={json.dumps(result)[:200]} rows={json.dumps(rows)[:300]}")
    if not rows or not result.get("minute_credited"):
        msg = f"no read credit for {card['id']}: rows={rows}"
        raise FlowError(msg)
    flow.step("stats.today's own minutes rose")
    old = int((state["today"] or {}).get("own_minutes") or 0)
    deadline, today = time.monotonic() + 15, dict[str, Any]()
    while time.monotonic() < deadline:
        today = flow.db.node("stats").get("today") or {}
        if int(today.get("own_minutes") or 0) > old:
            break
        time.sleep(1)
    else:
        msg = f"own_minutes still {today.get('own_minutes')} (was {old})"
        raise FlowError(msg)
    flow.note(f"today before={state['today']} after={today}")
    flow.home()
    flow.expect("Free chat", timeout=30)
    time.sleep(2)
    flow.shot("paid")


def drill(flow: Flow) -> None:
    """C6: with every card taught, Start opens the drill."""
    before = home_start(flow)
    flow.expect("Drill", timeout=20)
    result = flow.result("drill_next", before, timeout=20)
    if result.get("code"):
        msg = f"drill_next failed: {json.dumps(result)[:300]}"
        raise FlowError(msg)
    time.sleep(1)
    no_session_start(flow, before)
    no_error(flow)
    flow.shot("drill")


def empty(flow: Flow) -> None:
    """C6: nothing to read or drill: read mode's empty glyph, no error."""
    before = home_start(flow)
    flow.expect(EMPTY, timeout=25)
    no_session_start(flow, before)
    no_error(flow)
    flow.shot("empty")


def freedown(flow: Flow) -> None:
    """C9: free chat on a dead gateway shows its glyph; read mode still opens."""
    flow.home()
    flow.expect("Free chat", timeout=30)
    before = flow.rids()
    flow.tap("Free chat")
    result = flow.result("session_start", before, timeout=30)
    sent = new_nodes(flow, "session_start", before)
    body = (sent[0][1].get("req") or {}).get("body") or {} if sent else {}
    flow.note(f"body={json.dumps(body)[:200]}")
    if result.get("code") != "free_unavailable" or not body.get("free"):
        msg = (
            f"want a free session refused free_unavailable: {json.dumps(result)[:300]}"
        )
        raise FlowError(msg)
    time.sleep(3)
    flow.shot("freedown")
    after = home_start(flow)
    shown_card(flow, after, set())
    no_session_start(flow, after)
    flow.shot("freedown_read")


def phone(flow: Flow) -> None:
    """C12 at 412x915: front, flipped back and the rate glyphs all on screen."""
    before = home_start(flow)
    shown_card(flow, before, set())
    time.sleep(1)
    fit_check(flow, (FLIP,))
    flow.shot("phone_front")
    flip(flow)
    time.sleep(1)
    flow.shot("phone")
    fit_check(flow, RATE)


PHASES: Final[dict[str, Any]] = {
    "due": due,
    "read": read,
    "paid": paid,
    "drill": drill,
    "empty": empty,
    "freedown": freedown,
    "phone": phone,
}
