#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Agent-E2E F33: the model-free fallback and the per-module review.

Run by ``scripts/e2e_sandbox.sh flow F33 <phase>``, one call each (< 60 s),
each on the sandbox named (``S=scripts/e2e_sandbox.sh``):

* ``$S up --outage rate_limit --fallback due``: ``due`` (C3: Home's Start
  opens the Review on the due cards, no ``session_start``, no error glyph),
  then ``sheet`` (C15) and ``plan`` (C16) (``e2e_fallback_gate.py``).
* ``$S up --outage rate_limit --fallback read``: ``read`` (C4, C5: front,
  Flip, back with its excerpt, Got it on one card and Again on the next;
  ``taught`` + ``unchecked`` for both, a review rated 1 for Again), then
  ``paid`` (C5: one more card past 60 active seconds of the read run pays
  a ``read-`` row into the sandbox ledger and lifts ``own_minutes``), then
  ``$S restart --free-down`` and ``freedown`` (C9: the banner's free chat
  fails ``free_unavailable`` with its glyph; Start still opens read mode).
* ``... --fallback drill``: ``drill``; ``... --fallback empty``: ``empty`` (C6).
* ``... --fallback read``: ``phone`` (C12), at a 412x915 viewport.
* ``... --fallback read`` with OmniRoute up: ``free``, ``freewait`` (75 =
  again), ``freecheck`` (C9, ``e2e_fallback_free.py``).
* ``E2E_SUBJECT=product-and-design-taste $S up --fallback gate`` (no
  outage): ``gate`` (C7), then ``check``, ``checkwait`` (75 = again),
  ``checkfirst``, ``checkwait``, ``checkdone``, then ``checknext``,
  ``checkwrong``, ``checkreply``, ``checkagain`` (C8, ``e2e_fallback_check.py``).

* ``$S up`` (Claude up): ``pregen`` at once, then ``pregencheck`` (75 =
  again) (C10, ``e2e_fallback_pregen.py``).

Every phase screenshots its key frame as ``<out>_<phase>.png``; with
``E2E_SHOTS=DIR`` the prefix is ``DIR/f33``. Exit 0 = PASS.
"""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
import sys
from typing import Final

from e2e_cdp import Browser, CdpError
from e2e_fallback_check import PHASES as CHECK_PHASES
from e2e_fallback_free import PHASES as FREE_PHASES
from e2e_fallback_hold import PHASES as HOLD_PHASES
from e2e_fallback_phases import PHASES as START_PHASES
from e2e_fallback_pregen import PHASES as PREGEN_PHASES
from e2e_fallback_sheet import PHASES as SHEET_PHASES
from e2e_flow import Flow, FlowError

_logger = logging.getLogger(__name__)
PHASES: Final = {
    **START_PHASES,
    **SHEET_PHASES,
    **HOLD_PHASES,
    **FREE_PHASES,
    **CHECK_PHASES,
    **PREGEN_PHASES,
}
PHONE_PHASES: Final = frozenset({"phone", "planphone"})
PHONE: Final = (412, 915)  # C12's phone viewport (CSS px, scale 1)


def phone_viewport(browser: Browser, size: tuple[int, int]) -> None:
    """Pin the page's viewport and screen to ``size`` at device scale 1.

    The app's UI scale follows the screen (``ui_scale.dart``): a 4K Xvfb
    would double everything, and a window's toolbar would eat the height.
    """
    width, height = size
    browser.call(
        "Emulation.setDeviceMetricsOverride",
        width=width,
        height=height,
        deviceScaleFactor=1,
        mobile=False,
        screenWidth=width,
        screenHeight=height,
    )


def out_prefix(out: str, env: dict[str, str]) -> str:
    """``E2E_SHOTS/f33`` when that is set, else ``out``."""
    shots = env.get("E2E_SHOTS")
    return str(Path(shots) / "f33") if shots else out


def run(flow: Flow, phase: str) -> int:
    """Run ``phase``: 0 = PASS, 1 = FAIL (its step is logged), 75 = call again."""
    try:
        code = PHASES[phase](flow) or 0
    except (FlowError, CdpError, OSError, KeyError, TypeError, ValueError) as err:
        _logger.warning("FAIL F33 %s step %d: %s", phase, flow.n, err)
        for problem in flow.browser.problems[-10:]:
            _logger.info("  page %s", problem[:500])
        flow.shot(f"{phase}_fail")
        return 1
    if code:
        _logger.info("PENDING F33 %s: call it again", phase)
        return int(code)
    _logger.info("PASS F33 %s", phase)
    return 0


def main() -> int:
    """CLI entry: the arguments of ``e2e_drive.py`` (see the module docstring)."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("flow", choices=["F33"])
    parser.add_argument("phase", choices=sorted(PHASES))
    for name in ("--app", "--db", "--card", "--out", "--state", "--session"):
        parser.add_argument(name, required=name in {"--app", "--db", "--out"})
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--focus", type=Path)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--display", default=":97")
    parser.add_argument("--size", default="2560x1440")
    args = parser.parse_args()
    logging.basicConfig(stream=sys.stdout, format="%(message)s", level=logging.INFO)
    log = Path(f"{args.out}_{args.phase}_chrome.log")  # beside the default frames
    args.out = out_prefix(args.out, dict(os.environ))
    phone = args.phase in PHONE_PHASES
    width, height = PHONE if phone else (int(n) for n in args.size.split("x"))
    with Browser(args.display, log, (width, height)) as browser:
        if phone:
            phone_viewport(browser, PHONE)
        return run(Flow(args, browser), args.phase)


if __name__ == "__main__":
    raise SystemExit(main())
