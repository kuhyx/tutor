# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
from __future__ import annotations

import ast
from pathlib import Path

RELAY = Path(__file__).parents[1] / "relay"
FORBIDDEN = ("leetcode_guard",)


def imported(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            names.add(node.value)
    return names


def test_no_coach_module_reaches_the_gate_ledger() -> None:
    files = sorted(RELAY.glob("lc*.py"))
    assert len(files) >= 8
    for path in files:
        bad = [n for n in imported(path) if n.split(".")[0] in FORBIDDEN]
        assert not bad, f"{path.name} imports {bad}"
