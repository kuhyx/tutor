#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""F33's shared steps (``e2e_fallback.py``): Home's Start, read mode's card.

Every step reads the sandbox emulator's ``requests`` node for what the app
sent: Start must send no ``session_start`` while the outage is open, and
read mode's card is the newest ``read_next`` result (Home's Start reads
subjects in name order, so the seed's subject is not always the one shown).
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any, Final

from e2e_fallback_checks import PAGE_JS, outside
from e2e_flow import FlowError

if TYPE_CHECKING:
    from e2e_flow import Flow

# The Home session button's spoken labels (``session_entry.dart``).
START_LABELS: Final = ("Continue learning", "Learn")
LIVE_LABEL: Final = "Continue session"
FLIP: Final = "Flip card"
RATE: Final = ("Again", "Got it")
# Labels a failed request leaves on screen (``drill_parts.dart`` DrillFailed).
ERROR_LABELS: Final = ("Retry",)


def new_nodes(
    flow: Flow, kind: str, since: set[str]
) -> list[tuple[str, dict[str, Any]]]:
    """The ``kind`` requests sent after ``since``, oldest first."""
    return [
        (rid, node)
        for rid, node in sorted(flow.db.node("requests").items())
        if rid not in since and (node.get("req") or {}).get("kind") == kind
    ]


def home_start(flow: Flow, *, outage: bool = True) -> set[str]:
    """Open Home, check its Start is not a live session's, tap it.

    ``outage``: the banner's free-chat glyph must show first. Returns the
    request ids present before the tap.
    """
    flow.home()
    if outage:
        flow.expect("Free chat", timeout=30)
    flow.step("Home's Start is a new start, not a live session")
    live = flow.db.get("live")
    if live or flow.browser.find(LIVE_LABEL):
        msg = f"a live session would bypass the chooser: live={live}"
        raise FlowError(msg)
    label = next(
        (
            lab
            for lab in START_LABELS
            if (hit := flow.browser.wait_for(lab, 10)) and hit["text"] == lab
        ),
        None,
    )
    if label is None:
        msg = f"no Start button; saw: {flow.browser.page_text()[:400]!r}"
        raise FlowError(msg)
    before = flow.rids()
    flow.tap(label)
    return before


def no_session_start(flow: Flow, before: set[str]) -> None:
    """The app sent no chat request since ``before``."""
    flow.step("no session_start was sent")
    if sent := new_nodes(flow, "session_start", before):
        msg = f"session_start sent: {json.dumps(sent)[:300]}"
        raise FlowError(msg)


def no_error(flow: Flow) -> None:
    """No failure glyph on screen."""
    flow.step("no error glyph")
    if hits := [lab for lab in ERROR_LABELS if flow.browser.find(lab)]:
        msg = f"error glyph shown: {hits}"
        raise FlowError(msg)


def shown_card(flow: Flow, since: set[str], seen: set[str]) -> dict[str, Any]:
    """Read mode's front is up; the newest ``read_next`` card not in ``seen``."""
    flow.step("read mode shows a new card's front")
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        results = [
            n["result"]
            for _, n in new_nodes(flow, "read_next", since)
            if n.get("result")
        ]
        card = (results[-1].get("data") or {}).get("card") or {} if results else {}
        if card.get("id") and card["id"] not in seen and flow.browser.find(FLIP):
            flow.note(
                f"card={card['subject']}/{card['id']} module={card.get('module')} "
                f"excerpt={str(card.get('excerpt'))[:80]!r}"
            )
            return dict(card)
        time.sleep(0.5)
    msg = f"no new read card; saw: {flow.browser.page_text()[:400]!r}"
    raise FlowError(msg)


def flip(flow: Flow) -> None:
    """Flip the card: the back's two rate glyphs show, the flip glyph goes."""
    flow.tap(FLIP)
    flow.expect(*RATE)
    if flow.browser.find(FLIP):
        msg = "the flip glyph is still shown after the flip"
        raise FlowError(msg)


def rate(flow: Flow, label: str) -> dict[str, Any]:
    """Tap ``label`` (Again / Got it); the worker's ``read_rate`` result."""
    before = flow.rids()
    flow.tap(label)
    result = flow.result("read_rate", before, timeout=20)
    if not result.get("ok") or result.get("code"):
        msg = f"read_rate failed: {json.dumps(result)[:300]}"
        raise FlowError(msg)
    return dict(result.get("data") or {})


def dwell(flow: Flow, seconds: float) -> None:
    """Read for ``seconds`` (the read run's clock counts shown -> rated)."""
    flow.step(f"read for {seconds:.0f} s")
    time.sleep(max(0.0, seconds))


def fit_check(flow: Flow, labels: tuple[str, ...]) -> None:
    """Each of ``labels`` and every labelled node sit wholly in the viewport."""
    flow.step(f"nothing clipped: {', '.join(labels)} and every labelled node")
    size = flow.browser.evaluate("[innerWidth, innerHeight]")
    width, height = size if isinstance(size, list) else (0, 0)
    found = [hit for lab in labels for hit in all_of(flow, lab)]
    if len(found) < len(labels):
        msg = f"want {labels}, found {[h['text'] for h in found]}"
        raise FlowError(msg)
    leaves = flow.browser.evaluate(f"({PAGE_JS}).leaves()")
    every = [dict(h) for h in leaves] if isinstance(leaves, list) else []
    flow.note(f"viewport {width}x{height}; {len(every)} labelled nodes")
    for hit in found:
        flow.note(
            f"{hit['text']!r}: {[round(hit[k]) for k in ('left', 'top', 'right')]}"
            f" bottom {round(hit['bottom'])}"
        )
    if bad := outside(found + every, width, height):
        msg = f"clipped: {[(b['text'][:40], round(b['bottom'])) for b in bad][:6]}"
        raise FlowError(msg)


def all_of(flow: Flow, label: str, *, prefix: bool = False) -> list[dict[str, Any]]:
    """Every node labelled ``label`` (``prefix``: starting with it), with rects."""
    args = f"{json.dumps(label)}, {json.dumps(prefix)}"
    hits = flow.browser.evaluate(f"({PAGE_JS}).findAll({args})")
    return [dict(h) for h in hits] if isinstance(hits, list) else []
