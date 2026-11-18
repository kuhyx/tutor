#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Agent-E2E flow F17: a desktop page with no e2e key recovers it from the PC.

Runs on a fresh sandbox ``up`` (``e2e_sandbox.sh``): the server's
``/app/sync-passphrase`` serves once per process, and ``e2e_server.py`` points
it at the sandbox passphrase, never the real one. Model-free; one call.

1. the e2e build opened with ``nokey=1`` (keystore cleared, wrapper on) reaches
   Home with no lock and no click: the passphrase came from the server;
2. a second keyless load finds the route spent (404): the lock button is
   shown, so the manual entry stays the fallback.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from e2e_flow import FlowError

if TYPE_CHECKING:
    from e2e_flow import Flow

HOME = "Continue learning"
LOCKED = "Sync is locked"


def _keyless(flow: Flow) -> None:
    flow.step("open the app with an empty keystore (nokey=1)")
    flow.browser.open(f"{flow.args.app}?db={flow.args.db}&nokey=1")


def f17(flow: Flow) -> None:
    """Keyless page unlocks from the server once; then the lock is the fallback."""
    _keyless(flow)
    flow.expect(HOME, timeout=30)
    if flow.browser.find(LOCKED) is not None:
        msg = "the lock is still shown after recovery"
        raise FlowError(msg)
    flow.shot("recovered")
    _keyless(flow)
    flow.expect(LOCKED, timeout=30)
    flow.shot("fallback")
