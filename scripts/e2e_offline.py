#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Agent-E2E flow F34: the desktop app is offline-first from a cold start.

Runs on a fresh ``e2e_sandbox.sh up`` (no model), one call. The page loads
with ``keep=1`` (the real IndexedDB store, so a reload is a cold start that
finds what the last load kept); "offline" is the emulator's origin blocked
in Chrome (``Network.setBlockedURLs``), so its data survives for the check.

1. online: Home opens; the current subject is read off the page;
2. offline, cold: Home still opens (not the "Sync is locked" screen) with
   the offline cue and the same current subject; Progress shows the kept
   days, not "Could not load";
3. offline: "Learn this next" on another subject reads back at once;
4. online again, then a fresh profile with a memory store: the pick is on
   the database (the queued write was pushed).
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import re
import sys
import time
from typing import Final

from e2e_cdp import Browser
from e2e_flow import FlowError

_logger = logging.getLogger(__name__)
HOME: Final = "Continue learning"
OFFLINE: Final = "Offline"
LOCKED: Final = "Sync is locked"
PICK: Final = "Learn this next"
WAIT_S: Final = 15.0
# The current subject's Archive glyph follows "Cards" directly; every other
# row has "Learn this next" between them.
_CURRENT: Final = re.compile(r"CardsArchive (.+?)(?:Review \(|Plan|$)")
_DAY: Final = re.compile(r"\d{4}-\d{2}-\d{2}")


def current(text: str) -> str:
    """The title of the current subject on Home (FlowError when none)."""
    if hit := _CURRENT.search(text):
        return hit.group(1)
    msg = f"no current subject; saw: {text[:300]!r}"
    raise FlowError(msg)


def _home(b: Browser, url: str) -> str:
    """Open ``url``, wait for Home, return its text (FlowError otherwise)."""
    b.open(url)
    if b.wait_for(HOME, WAIT_S) is None:
        msg = f"Home did not open; saw: {b.page_text()[:300]!r}"
        raise FlowError(msg)
    return b.page_text()


def _block(b: Browser, db: str, *, offline: bool) -> None:
    b.call("Network.enable")
    b.call("Network.setBlockedURLs", urls=[f"{db}/*"] if offline else [])


def _check(ok: object, what: str, b: Browser) -> None:
    if not ok:
        msg = f"{what}; saw: {b.page_text()[:300]!r}"
        raise FlowError(msg)
    _logger.info("ok: %s", what)


def run(args: argparse.Namespace) -> None:
    """Steps 1-4 (module docstring); screenshots under ``--out``."""
    out = Path(args.out)
    keep = f"{args.app}?db={args.db}&keep=1"
    with Browser(args.display, Path(f"{out}_chrome.log"), (2560, 1440)) as b:
        before = current(_home(b, keep))
        _block(b, args.db, offline=True)
        text = _home(b, keep)
        b.screenshot(Path(f"{out}_home_offline.png"))
        _check(LOCKED not in text and OFFLINE in text, "cold start offline", b)
        _check(current(text) == before, f"kept current subject {before!r}", b)
        hit = b.find(PICK)
        _check(hit, "a subject to pick", b)
        b.click(hit or {})
        time.sleep(1)
        picked = current(b.page_text())
        _check(picked != before, f"offline pick reads back: {picked!r}", b)
        b.open(f"{keep}&screen=progress")
        time.sleep(4)
        b.screenshot(Path(f"{out}_progress_offline.png"))
        page = b.page_text()
        _check(_DAY.search(page) and "Could not load" not in page, "Progress", b)
        _block(b, args.db, offline=False)
        _home(b, keep)
        time.sleep(2)  # the outbox flushes on the online Home load
    with Browser(args.display, Path(f"{out}_fresh.log"), (2560, 1440)) as fresh:
        text = _home(fresh, f"{args.app}?db={args.db}")
        _check(current(text) == picked, f"pick on the database: {picked!r}", fresh)


def main() -> int:
    """CLI entry: the arguments ``e2e_sandbox.sh flow`` passes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("flow", choices=["F34"])
    parser.add_argument("phase", choices=["all"])
    for name in ("--card", "--session", "--subject", "--data", "--focus"):
        parser.add_argument(name)
    for name in ("--app", "--db", "--out", "--state"):
        parser.add_argument(name, required=True)
    parser.add_argument("--display", default=":97")
    args = parser.parse_args()
    logging.basicConfig(stream=sys.stdout, format="%(message)s", level=logging.INFO)
    try:
        run(args)
    except (FlowError, OSError) as err:
        _logger.warning("FAIL F34: %s", err)
        return 1
    _logger.info("PASS F34")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
