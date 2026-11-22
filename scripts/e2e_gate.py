#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""F21: Next leads straight into the module gate's review, then on.

kuhy, 2026-11-22: finish a module, pass its cards (plus the subject's due
ones), then the next module starts; no cap, no waiting, no panel of icons.

* ``seed <data> --subject S`` (``e2e_sandbox.sh up --gate``): every card
  before S's first unstarted module N is taught; every taught card is
  reviewed Good a minute ago, except the last two of the module M right
  before N, which are taught again an hour ago (not passed since). The
  worker's own pick must then refuse with exactly those two as
  ``gate_cards``. Writes ``<sandbox>/f21_seed.json``.
* send: Home -> Continue learning: the review of M opens at once with
  "2 left" (the passed cards stay out: the image-2 bug), no old panel;
  Show answer -> Good twice; the app sends ``session_start`` again with
  no tap.
* check (after ``wait``: a model turn): that start is ok and the live card
  is in N, with the session's composer on screen.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys
import time
from typing import TYPE_CHECKING, Any, Final
import uuid

from e2e_composer_glyphs import glyphs
from e2e_flow import BLOCKED_CTAS, FlowError
from e2e_seed import DAY_MS, GAP_MS, GOOD, SeedError, _sandboxed, _stop_newest

from tutor.curriculum import rules
from tutor.curriculum.context import Context
from tutor.curriculum.errors import RequestError
from tutor.curriculum.eventlog import review_event, worker_event
from tutor.curriculum.fold import Fold, fold
from tutor.curriculum.pick import pick, started

if TYPE_CHECKING:
    from e2e_flow import Flow, State

    from tutor.curriculum.records import Module

_logger = logging.getLogger(__name__)
UNPASSED: Final = 2
REVEAL: Final = "Show answer (Space)"


def _modules(view: rules.View, folded: Fold) -> tuple[list[Module], Module]:
    """The open modules before S's first unstarted one, and that one."""
    earlier: list[Module] = []
    for module in view.plan.modules:
        if module.status == "generating":
            msg = f"{module.id} is being written: the gate would show the pencil"
            raise SeedError(msg)
        if module.status not in rules.OPEN or not counted_ids(view, module, folded):
            continue
        if earlier and not started(view, folded, module.id):
            return earlier, module
        earlier.append(module)
    msg = f"{view.subject} has no unstarted module after a taught one"
    raise SeedError(msg)


def counted_ids(view: rules.View, module: Module, folded: Fold) -> list[str]:
    """The module's counted card ids, in order."""
    return [cid for cid, _ in rules.counted(view, module.id, folded)]


def _check_pick(view: rules.View, data: Path, now: int, want: list[str]) -> None:
    """The worker's own pick refuses with exactly ``want`` to review."""
    ctx = Context(data, device=str(uuid.uuid4()))
    try:
        got = pick(view, fold(ctx.log.read()), None, now)
    except RequestError as err:
        raw = err.extra.get("gate_cards")
        cards = [str(c) for c in raw] if isinstance(raw, list) else []
        if sorted(cards) == sorted(want):
            return
        msg = f"gate_cards {cards}, want {want} ({err.code})"
        raise SeedError(msg) from err
    msg = f"the worker would teach {got}, not refuse"
    raise SeedError(msg)


def seed(data: Path, subject: str, now: int) -> dict[str, Any]:
    """Seed the gate before S's next module (module doc)."""
    _sandboxed(data)
    ctx = Context(data, device=str(uuid.uuid4()))
    meta = ctx.subjects.meta(subject)
    plan = ctx.subjects.plan(subject)
    if plan is None:
        msg = f"{subject} has no plan"
        raise SeedError(msg)
    view = rules.View(
        subject, plan, ctx.subjects.cards(subject), meta.title if meta else ""
    )
    folded = fold(ctx.log.read())
    earlier, nxt = _modules(view, folded)
    last = earlier[-1]
    unpassed = counted_ids(view, last, folded)[-UNPASSED:]
    # Taught by the sandbox worker, reviewed by a fresh "app": a review by a
    # device that also wrote a ``taught`` is a drill pick (fold rule 6).
    worker = (data / "device_id").read_text(encoding="utf-8").strip()
    events: list[dict[str, Any]] = []
    for module in view.plan.modules:
        for cid, state in rules.counted(view, module.id, folded):
            ref, rev = (subject, cid), view.cards[cid].rev
            if cid in unpassed:
                at = now - 3_600_000
                events.append(worker_event("taught", ref, dev=worker, at=at))
                continue
            if not state.taught and module in earlier:
                at = now - 2 * DAY_MS
                events.append(worker_event("taught", ref, dev=worker, at=at))
            elif not state.taught:
                continue
            span = (now - GAP_MS - 5000, now - GAP_MS)
            events.append(review_event(ref, GOOD, dev=ctx.device, span=span, rev=rev))
    ctx.log.append(events)
    _stop_newest(data, subject)
    _check_pick(view, data, now, unpassed)
    out = {
        "module": last.id,
        "module_title": last.title,
        "next_module": nxt.id,
        "unpassed": unpassed,
        "passed": [c for c in counted_ids(view, last, folded) if c not in unpassed],
    }
    (data.parent / "f21_seed.json").write_text(json.dumps(out))
    return out


def _seed_of(flow: Flow) -> dict[str, Any]:
    """What ``seed`` wrote beside the sandbox data dir."""
    path = Path(flow.args.data).parent / "f21_seed.json"
    return dict(json.loads(path.read_text()))


def _shown(flow: Flow, *parts: str, timeout: float = 20) -> str:
    """The page text once it holds every one of ``parts``.

    The review bar's label runs together with Back, so a label-prefix
    find misses it.
    """
    flow.step(f"on screen: {', '.join(parts)}")
    deadline = time.monotonic() + timeout
    while True:
        text = flow.browser.page_text()
        if all(p in text for p in parts):
            return text
        if time.monotonic() > deadline:
            msg = f"want {parts}; saw: {text[:400]!r}"
            raise FlowError(msg)
        time.sleep(0.5)


def f21_send(flow: Flow) -> State:
    """Continue -> the review opens -> pass it -> Next goes out by itself."""
    seed_ = _seed_of(flow)
    flow.home()
    before = flow.rids()
    flow.tap("Continue learning", timeout=30)
    result = flow.start_result(before)
    after = flow.rids()
    flow.step("the refusal names exactly the unpassed cards")
    if sorted(result.get("gate_cards") or []) != sorted(seed_["unpassed"]):
        msg = f"want gate_cards {seed_['unpassed']}, got {json.dumps(result)[:300]}"
        raise FlowError(msg)
    text = _shown(flow, f"Review: {seed_['module_title']}", f"{UNPASSED} left")
    if hits := [
        b for b in (*BLOCKED_CTAS, f"Review {seed_['module_title']}") if b in text
    ]:
        msg = f"the old panel shows: {hits}"
        raise FlowError(msg)
    flow.shot("review")
    for n in range(UNPASSED):
        flow.step(f"card {n + 1}: wait 1.5 s (the 1 s presence floor), then Good")
        time.sleep(1.5)
        flow.tap(REVEAL)
        flow.tap("3 Good")
    rid = flow.request("session_start", after, timeout=30)
    return {"rid": rid, **seed_}


def f21_check(flow: Flow, state: State) -> None:
    """The second start is ok and teaches the next module's card."""
    flow.step("the second session_start result is ok")
    result = flow.result_of(str(state["rid"]))
    flow.note(f"result={json.dumps(result)[:300]}")
    if not result.get("ok"):
        msg = f"refused again: {result.get('code')}: {json.dumps(result)[:300]}"
        raise FlowError(msg)
    flow.step(f"the live card is in {state['next_module']}")
    card = str(flow.db.node("live").get("card"))
    cards = Context(Path(flow.args.data), device="e2e").subjects.cards(
        flow.args.subject
    )
    if card not in cards or cards[card].module != state["next_module"]:
        msg = f"live card {card} is not in {state['next_module']}"
        raise FlowError(msg)
    flow.screen("/session")
    flow.expect("Send", timeout=20)
    flow.shot("started")
    glyphs(flow, state)


def main() -> int:
    """CLI entry: ``seed`` (module doc)."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("what", choices=["seed"])
    parser.add_argument("data", type=Path)
    parser.add_argument("--subject", required=True)
    args = parser.parse_args()
    logging.basicConfig(stream=sys.stderr, format="%(message)s")
    try:
        found = seed(args.data, args.subject, int(time.time() * 1000))
    except SeedError as err:
        _logger.warning("e2e_gate: %s", err)  # `up` stops on exit 1
        return 1
    # The seed's evidence in `up`'s output.
    sys.stdout.write(f"e2e seed F21: {json.dumps(found)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
