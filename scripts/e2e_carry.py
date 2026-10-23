#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Agent-E2E flow F6: the carry-over bank (``DOCS-contract-carry.md``).

Runs on a sandbox brought ``up --as-of "<a day after CARRY_FROM> HH:MM"
--carry N``: the worker's clock starts at that moment (libfaketime) and
``e2e_seed.py carry`` signed N minutes ending the day before into the
SANDBOX ledger with the sandbox key (never the real one).

* check: the sandbox ledger holds ``carry-<today>-m<n>`` rows paying the
  target the contract's formula gives from the ledger's own non-carry rows
  (computed here, independently of ``tutor.carry``); ``stats.today``
  shows the same ``prepaid`` and ``banked`` (both > 0); Home shows
  "Banked B min · prepaid P". The ledger is saved to the flow's state.
* again (after ``scripts/e2e_sandbox.sh restart``, a second worker start on
  the same sandbox): the ledger is byte for byte what check saw, so the
  startup spend, the curriculum sync and the stats publish wrote no
  duplicate.
"""

from __future__ import annotations

from datetime import date, timedelta
import json
from pathlib import Path
import re
import time
from typing import TYPE_CHECKING, Any

from e2e_flow import Flow, FlowError, State
import earned_time

from tutor.credit import local_day

if TYPE_CHECKING:
    from collections.abc import Iterable

CARRY_FROM = date(2026, 10, 23)  # DOCS-contract-carry.md
BANK_CAP, DAY_CAP = 100, 160
CARRY = re.compile(r"carry-(\d{4}-\d{2}-\d{2})-m(\d+)")


def _paid(rows: Iterable[dict[str, Any]], key: bytes) -> list[tuple[str, str, int]]:
    """``(entry_id, local day, minutes)`` of the verified credit rows."""
    out = []
    for row in rows:
        detail = row.get("detail") or {}
        if row.get("kind") == "credit" and earned_time.verified(row, key):
            day = local_day(float(detail["ended_at"]))[0]
            out.append((str(row["entry_id"]), day, int(detail.get("minutes", 15))))
    return out


def expected(paid: list[tuple[str, str, int]], today: date) -> tuple[int, int]:
    """``(prepaid, banked)`` today by the contract's formula.

    Carry rows of earlier days count as what the ledger holds.
    """
    total: dict[str, int] = {}
    spent: dict[str, int] = {}
    for entry, on, minutes in paid:
        total[on] = total.get(on, 0) + minutes
        if CARRY.fullmatch(entry):
            spent[on] = spent.get(on, 0) + minutes

    def after(balance: int, day: date, own: int, carry: int) -> int:
        quota = int(earned_time.tutor_quota_for(day))
        deposit = max(0, min(own + carry, DAY_CAP) - quota)
        return max(0, min(BANK_CAP, balance - carry + deposit))

    balance, day = 0, CARRY_FROM
    while day < today:
        iso = day.isoformat()
        carry = spent.get(iso, 0)
        balance = after(balance, day, total.get(iso, 0) - carry, carry)
        day += timedelta(days=1)
    iso = today.isoformat()
    target = min(balance, int(earned_time.tutor_quota_for(today)))
    own = total.get(iso, 0) - spent.get(iso, 0)
    return target, after(balance, today, own, target)


def _ledger(flow: Flow) -> tuple[list[dict[str, Any]], bytes]:
    data = Path(flow.args.data)
    rows = json.loads((data / "ledger.json").read_text()).get("entries", [])
    key = (data.parent / "test.key").read_bytes().strip()
    return rows, key


def f6_check(flow: Flow) -> State:
    """Carry rows, stats and the Home note agree with the formula."""
    flow.step("stats.today from the emulator")
    today = flow.db.node("stats").get("today") or {}
    flow.note(f"today={ {k: today.get(k) for k in ('day', 'banked', 'prepaid')} }")
    if not today.get("day"):
        msg = "no stats.today (worker not up?)"
        raise FlowError(msg)
    flow.step(f"the sandbox ledger pays {today['day']}'s carry")
    if not (Path(flow.args.data) / "ledger.json").is_file():
        msg = "no sandbox ledger (up without --carry?)"
        raise FlowError(msg)
    rows, key = _ledger(flow)
    paid = _paid(rows, key)
    carry = [(e, m) for e, d, m in paid if d == today["day"] and CARRY.fullmatch(e)]
    want_prepaid, want_banked = expected(paid, date.fromisoformat(today["day"]))
    flow.note(f"carry rows {carry}; want prepaid={want_prepaid} banked={want_banked}")
    ids = [str(r.get("entry_id")) for r in rows]
    if len(ids) != len(set(ids)):
        msg = f"duplicate entry ids in the ledger: {sorted(ids)}"
        raise FlowError(msg)
    if not carry or sum(m for _, m in carry) != want_prepaid or want_prepaid <= 0:
        msg = f"carry rows {carry}, want {want_prepaid} minutes"
        raise FlowError(msg)
    flow.step("stats.today shows the same prepaid and banked")
    got = (today.get("prepaid"), today.get("banked"))
    if got != (want_prepaid, want_banked) or want_banked <= 0:
        msg = f"stats prepaid/banked {got}, want {(want_prepaid, want_banked)} > 0"
        raise FlowError(msg)
    flow.home()
    note = f"Banked {want_banked} min · prepaid {want_prepaid}"
    flow.step(f'Home shows "{note}"')
    # The Today card's lines merge into one semantics label: match inside it.
    deadline = time.monotonic() + 30
    while note not in flow.browser.page_text():
        if time.monotonic() > deadline:
            msg = f"no {note!r}; saw: {flow.browser.page_text()[:400]!r}"
            raise FlowError(msg)
        time.sleep(0.5)
    flow.shot("home")
    return {"ledger": (Path(flow.args.data) / "ledger.json").read_text()}


def f6_again(flow: Flow, state: State) -> None:
    """After a second worker start, the ledger is unchanged."""
    # ``restart`` deleted ``stats``: it is back once the new worker ran its
    # startup spend and published (each publish spends first).
    flow.step("stats republished by the restarted worker")
    deadline = time.monotonic() + 30
    while not (flow.db.node("stats").get("today") or {}).get("day"):
        if time.monotonic() > deadline:
            msg = "no stats.today in 30 s (run scripts/e2e_sandbox.sh restart first)"
            raise FlowError(msg)
        time.sleep(0.5)
    flow.step("the ledger is what check saw: no duplicate carry row")
    now = (Path(flow.args.data) / "ledger.json").read_text()
    if now != state["ledger"]:
        rows, key = _ledger(flow)
        msg = f"the ledger changed: {[e for e, _, _ in _paid(rows, key)]}"
        raise FlowError(msg)
    rows, key = _ledger(flow)
    flow.note(
        f"{len(rows)} rows, unchanged; carry: "
        f"{[e for e, _, _ in _paid(rows, key) if CARRY.fullmatch(e)]}"
    )
