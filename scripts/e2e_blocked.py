#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""F12: a forced ``no_card_left`` reaches the app as a kind, drawn as a glyph.

Run after ``scripts/e2e_sandbox.sh up --nocard due|review`` (``e2e_seed.py
nocard`` writes ``<sandbox>/f12_seed.json`` with the expected kind). Home ->
Continue learning; the worker's result carries ``kind`` beside the old
``error`` and ``next`` (DOCS-relay-kinds.md); the app speaks its own
sentence for it, never the worker's ``error``; a screenshot shows the cue.
``review`` (2026-11-22): the result lists ``gate_cards`` and the app opens
that review at once instead (F21 drives it to the end).
"""

from __future__ import annotations

import json
from pathlib import Path
import time
from typing import TYPE_CHECKING

from e2e_flow import FlowError

if TYPE_CHECKING:
    from e2e_flow import Flow

_SPOKEN = "No card left to teach"


def f12(flow: Flow) -> None:
    """The blocked cue for a forced ``no_card_left`` (module doc)."""
    seed = json.loads((Path(flow.args.data).parent / "f12_seed.json").read_text())
    flow.home()
    before = flow.rids()
    flow.tap("Continue learning", timeout=30)
    result = flow.start_result(before)
    flow.step("the result has kind, error and next (C12)")
    if result.get("code") != "no_card_left" or result.get("kind") != seed["kind"]:
        msg = f"want no_card_left/{seed['kind']}, got {json.dumps(result)[:300]}"
        raise FlowError(msg)
    if not result.get("error") or not result.get("next"):
        msg = f"the old fields are gone: {json.dumps(result)[:300]}"
        raise FlowError(msg)
    if seed["kind"] == "blocked_no_card_review":
        flow.step("gate_cards are listed and their review opens at once")
        if not result.get("gate_cards"):
            msg = f"no gate_cards: {json.dumps(result)[:300]}"
            raise FlowError(msg)
        flow.expect("Review: ", timeout=20)
        flow.shot("review")
        return
    flow.step("the cue speaks the app's sentence, not the worker's")
    # The glyph's spoken line runs together with its one-word tooltip, so
    # look in the page text, not for a label prefix.
    deadline = time.monotonic() + 15
    while _SPOKEN not in (text := flow.browser.page_text()):
        if time.monotonic() > deadline:
            msg = f"no blocked cue; saw: {text[:400]!r}"
            raise FlowError(msg)
        time.sleep(0.5)
    if str(result["error"]) in text:
        msg = f"the worker's error is on the page: {result['error']!r}"
        raise FlowError(msg)
    print(f"  spoken: {next(t for t in text.splitlines() if _SPOKEN in t)!r}")
    flow.shot("blocked")
