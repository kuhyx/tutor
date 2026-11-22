#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""What the C4 flows (``e2e_learn.py``, ``e2e_learn_gate.py``) read on disk.

The sandbox's transcripts, its ``c4_seed.json``, and the tutor's signed rows
(C1 credit rows in ``ledger.json``, C2 rows in ``module_state.json``), each
verified with gatelock's HMAC check and the sandbox key, never the real one.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from e2e_flow import Flow, FlowError, State
from e2e_follow_up import _ledger
from e2e_takeover import LC, MODULE
from gatelock import log_integrity


def transcripts(flow: Flow) -> set[str]:
    """The session transcripts on disk."""
    return {p.stem for p in (flow.args.data / "sessions").glob("*.jsonl")}


def seed(flow: Flow) -> dict[str, str]:
    """``up --learn``'s ``c4_seed.json``: the one untaught card left."""
    path = flow.args.data.parent / "c4_seed.json"
    return dict(json.loads(path.read_text(encoding="utf-8")))


def _key(flow: Flow) -> Path:
    return Path(flow.args.data.parent, "test.key")


def _on_module(row: dict[str, Any], flow: Flow) -> bool:
    detail = row.get("detail") or {}
    return (
        detail.get("subject") == LC
        and detail.get("module") == MODULE
        and log_integrity.verify_entry_hmac(row, key_file=_key(flow))
    )


def ledger_ids(flow: Flow) -> list[str]:
    """The credit rows' entry ids now."""
    return [str(r["entry_id"]) for r in _ledger(flow.args.data)]


def credit_paid(flow: Flow, state: State) -> None:
    """C1: a new verified credit row of the session names subject and module."""
    flow.step("C1: a new verified credit row with detail.subject and detail.module")
    old, sid = set(state["ledger"]), str(state["sid"])
    rows = [
        r
        for r in _ledger(flow.args.data)
        if r["entry_id"] not in old and str(r["entry_id"]).startswith(f"{sid}-m")
    ]
    flow.note(f"new rows: {json.dumps(rows)[:400]}")
    if not [r for r in rows if _on_module(r, flow)]:
        msg = f"no verified credit row on {LC}/{MODULE} for {sid}"
        raise FlowError(msg)


def module_done(flow: Flow) -> bool | None:
    """The latest sandbox-verified C2 row of LC/MODULE (None: no such row)."""
    path = flow.args.data / "module_state.json"
    rows = json.loads(path.read_text(encoding="utf-8")).get("entries", [])
    mine = [r for r in rows if _on_module(r, flow)]
    flow.note(f"verified {LC}/{MODULE} rows: {[r['entry_id'] for r in mine]}")
    return bool(mine[-1]["detail"]["done"]) if mine else None
