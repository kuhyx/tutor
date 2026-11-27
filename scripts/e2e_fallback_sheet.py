#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""F33's sheet and plan phases (``e2e_fallback.py``; part e79be0be-1).

* ``sheet`` (C15; ``up --fallback due``): the subject tile's review glyph
  opens the module sheet, whose rows match the server's due counts per
  module; a row opens Review with that many cards left.
* ``plan`` (C16, same sandbox): S's Plan (opened from its Home tile) shows
  a due button exactly on the modules with due cards; the smallest opens
  Review with that many left; passing them (Good) drops that one button.
* ``planphone`` (C16 at 412x915): S's Home tile opens its Plan: the same
  due buttons on the phone's module tiles.
"""

from __future__ import annotations

from pathlib import Path
import time
from typing import TYPE_CHECKING, Any, Final

from e2e_fallback_checks import due_by_module, due_labels, left_count, module_titles
from e2e_fallback_steps import all_of
from e2e_flow import FlowError

from tutor.curriculum.context import Context

if TYPE_CHECKING:
    from e2e_flow import Flow

SCROLLS: Final = 6  # Plan pages scanned for due buttons
ROW_PX: Final = 8  # a tile's glyphs share one row
PAGES: Final = 6  # phone Plan grid pages scanned
PAGE_PX: Final = 412  # one page of it: the phone width


def _want(flow: Flow) -> dict[str, int]:
    """Module title -> due count by the server's fold, modules with due only."""
    subject = flow.args.subject
    titles = module_titles(Path(flow.args.data), subject)
    found = due_by_module(Path(flow.args.data), subject, int(time.time() * 1000))
    want = {titles[m]: n for m, n in found.items() if n and m in titles}
    flow.note(f"server due by module: {want}")
    if not want:
        msg = f"{subject} has no module with due cards"
        raise FlowError(msg)
    return want


def _review_left(flow: Flow, title: str, count: int) -> None:
    """The Review of module ``title`` is open with ``count`` cards left.

    Its title and count run together with Back in the page text (no own node).
    """
    flow.step(f"Review: {title}, {count} left")
    deadline, text = time.monotonic() + 20, ""
    while time.monotonic() < deadline:
        text = flow.browser.page_text()
        if f"Review: {title}" in text and left_count(text) is not None:
            break
        time.sleep(0.5)
    if f"Review: {title}" not in text or left_count(text) != count:
        msg = f"want Review: {title} with {count} left; saw: {text[:300]!r}"
        raise FlowError(msg)


def tile_glyph(hits: list[dict[str, Any]], drill: dict[str, Any]) -> dict[str, Any]:
    """The one hit off the row of Home's Drill glyph (Home's own Review sits there)."""
    home = min(hits, key=lambda h: abs(h["top"] - drill["top"]))
    mine = [h for h in hits if h is not home]
    if len(mine) != 1:
        msg = f"want one subject review glyph beside Home's, got {mine}"
        raise FlowError(msg)
    return mine[0]


def home_tile_glyph(flow: Flow) -> dict[str, Any]:
    """On Home (log synced: its due count shows), S's tile review glyph."""
    flow.home()
    flow.expect("Review (", timeout=30)
    flow.step("the subject tile's review glyph, not Home's (beside Drill)")
    hits = [
        h for h in all_of(flow, "Review (", prefix=True) if h["text"].endswith(" due)")
    ]
    drill = all_of(flow, "Drill")
    flow.note(f"{[(h['text'], round(h['left']), round(h['top'])) for h in hits]}")
    if not hits or not drill:
        msg = f"no review glyph with a due count ({len(hits)}) or no Drill glyph"
        raise FlowError(msg)
    return tile_glyph(hits, drill[0])


def sheet(flow: Flow) -> None:
    """C15: the tile's review glyph -> the module sheet -> a module's Review."""
    want = _want(flow)
    flow.browser.click(home_tile_glyph(flow))
    flow.expect("Review all (", timeout=15)
    time.sleep(1)
    shown = due_labels([h["text"] for h in all_of(flow, "Review ", prefix=True)])
    flow.step(f"sheet rows {shown} match the server")
    if shown != want:
        msg = f"sheet rows {shown}, want {want}"
        raise FlowError(msg)
    flow.shot("sheet")
    title, count = next(iter(shown.items()))
    flow.tap(f"Review {title} ({count} due)")
    _review_left(flow, title, count)
    flow.shot("sheet_review")


def scan_due(flow: Flow) -> dict[str, int]:
    """Every ``Review <module> (N due)`` button of the Plan, scrolled through."""
    found: dict[str, int] = {}
    for _ in range(SCROLLS):
        found |= due_labels([h["text"] for h in all_of(flow, "Review ", prefix=True)])
        flow.browser.scroll(500)
        time.sleep(0.4)
    flow.browser.scroll(-500 * SCROLLS)
    time.sleep(0.5)
    return found


def _match(flow: Flow, shown: dict[str, int], want: dict[str, int]) -> None:
    flow.step(f"plan due buttons match the server ({len(want)} modules)")
    if shown != want:
        extra = {k: v for k, v in shown.items() if want.get(k) != v}
        missing = {k: v for k, v in want.items() if shown.get(k) != v}
        msg = f"plan due buttons differ: shown {extra}, want {missing}"
        raise FlowError(msg)


def plan(flow: Flow) -> None:
    """C16: due buttons on exactly the modules with due cards; one opens Review."""
    want = _want(flow)
    # From Home, as kuhy goes: a deep link opens Plan before the fresh
    # profile's log has synced, and Plan refolds only on a catalog change.
    glyph = home_tile_glyph(flow)
    flow.step("the same tile's Plan glyph")
    row = [h for h in all_of(flow, "Plan") if abs(h["top"] - glyph["top"]) < ROW_PX]
    if not row:
        msg = f"no Plan glyph in the row of {glyph}"
        raise FlowError(msg)
    flow.browser.click(row[0])
    flow.expect("Review ", timeout=30)
    time.sleep(1)
    _match(flow, scan_due(flow), want)
    flow.shot("plan")
    title, count = min(want.items(), key=lambda kv: kv[1])
    flow.tap(f"Review {title} ({count} due)")
    _review_left(flow, title, count)
    flow.shot("plan_review")
    for n in range(count):
        flow.step(f"card {n + 1}: wait 1.5 s, then Good")
        time.sleep(1.5)
        flow.tap("Show answer (Space)")
        flow.tap("3 Good")
    time.sleep(1)
    flow.tap("Back")
    flow.expect("Review ", timeout=20)
    time.sleep(1.5)
    _match(flow, scan_due(flow), {k: v for k, v in want.items() if k != title})
    flow.shot("plan_after")


def swipe_due(flow: Flow) -> dict[str, int]:
    """The phone Plan's due buttons, page by page of its sideways tile grid."""
    found: dict[str, int] = {}
    for _ in range(PAGES):
        hits = [
            h
            for h in all_of(flow, "Review ", prefix=True)
            if h["text"].endswith(" due)")
        ]
        found |= due_labels([h["text"] for h in hits])
        if not hits:
            break
        flow.browser.call(
            "Input.dispatchMouseEvent",
            type="mouseWheel",
            x=hits[0]["x"],
            y=hits[0]["y"],
            deltaX=PAGE_PX,
            deltaY=0,
        )
        time.sleep(0.8)
    flow.note(f"pages scanned; {len(found)} modules with a due button")
    return found


def planphone(flow: Flow) -> None:
    """C16 on the phone: the Plan's module tiles carry the same due buttons."""
    want = _want(flow)
    flow.home()
    flow.expect("Review (", timeout=30)  # the local log is folded
    # In the app, not a deep link: a reload's Plan folds an unsynced log.
    meta = Context(Path(flow.args.data), device="e2e").subjects.meta(flow.args.subject)
    flow.tap(meta.title if meta else flow.args.subject)
    flow.expect("Modules", timeout=30)
    time.sleep(1.5)
    flow.shot("planphone")
    _match(flow, swipe_due(flow), want)


PHASES: Final[dict[str, Any]] = {"sheet": sheet, "plan": plan, "planphone": planphone}
