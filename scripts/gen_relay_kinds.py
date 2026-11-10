#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Write ``contract/relay_kinds.json`` from ``tutor.relay.kinds`` (DOCS-relay-kinds.md).

The app's parity test reads the file; ``tutor/tests/test_relay_kinds.py``
fails when it drifts from the mapping. Run after changing a kind or phase.
"""

from __future__ import annotations

import json
from pathlib import Path

from tutor.relay.claims import PHASES
from tutor.relay.kinds import golden

_OUT = Path(__file__).resolve().parents[1] / "contract" / "relay_kinds.json"


def main() -> None:
    """Write the golden file."""
    text = json.dumps(golden(PHASES), indent=2, ensure_ascii=False) + "\n"
    _OUT.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
