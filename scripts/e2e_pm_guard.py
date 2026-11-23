#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Flow F32's guard side: leetcode-guard's own e2e roles, with real slugs.

Runs under the SYSTEM python (the guard's deploy path: user site-packages)
from the guard checkout ``$E2E_ROOT``, under the scratch ``$HOME`` and key
the driver sets: ``scripts.e2e_theory_roles`` (``pool``, ``lock``,
``harvest``, ``status``) fakes LeetCode and the HMAC key and runs the real
entry points. Its scratch pool names made-up prefix-sums slugs; here the unit
claims four of kuhy's real solves instead (``$E2E_PM_SLUGS``), so the C6 row
names problems whose mirrored code the post-mortem reads. One role is added,
``unit``: the unit dict the guard's MCP server and phone snapshot show
(``_status_unit.unit_dict``, with ``cards_taught`` / ``cards_total``), which
``--status`` does not print. Usage: ``e2e_pm_guard.py ROLE [ARGS...]``.
"""

from __future__ import annotations

from datetime import datetime
import importlib
import json
import os
from pathlib import Path
import sys


def main() -> int:
    """Patch the scratch pool's prefix-sums slugs, then run the role."""
    root = Path(os.environ["E2E_ROOT"]).resolve()
    if (
        not Path(os.environ["HOME"])
        .resolve()
        .is_relative_to(Path(os.environ["E2E_PM_CASE"]).resolve())
    ):
        sys.exit("refused: HOME is not the case's scratch home")
    sys.path.insert(0, str(root))
    roles = importlib.import_module("scripts.e2e_theory_roles")
    slugs = tuple(s for s in os.environ["E2E_PM_SLUGS"].split(",") if s)
    roles.__dict__["EASY"] = {"prefix-sums": slugs, "stack-queue": ("sq-one", "sq-two")}
    if sys.argv[1] == "unit":
        roles.fake_world()  # the role module's scratch key and fake LeetCode
        return unit(roles.KEY)
    return int(roles.main(sys.argv[1], sys.argv[2:]))


def unit(key: Path) -> int:
    """Print the guard's unit dict (display only) for today."""
    constants = importlib.import_module("leetcode_guard._constants")
    ledger_io = importlib.import_module("leetcode_guard._ledger_io")
    status = importlib.import_module("leetcode_guard._status_unit")
    path = constants.LEDGER_FILE
    ledger = ledger_io.load_ledger(path, key_file=key)
    today = datetime.now().astimezone().date()
    found = status.gather_unit(ledger, path, day=today, key_file=key)
    print(json.dumps(status.unit_dict(found), default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
