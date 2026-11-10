#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Pre-commit pytest gate: pass stamp, else the tests that reach the change.

The hook must always finish under the 60 s per-action cap, at any machine load.
1. A pass stamp for the staged tree (``git write-tree``, see ``pytest_store``)
   written by ``scripts/pytest_stamp.py run`` passes instantly.
2. No stamp and a small change (under a quarter of the test files reach it):
   run those tests inline with 100% line and branch coverage on exactly the
   changed source files.
3. No stamp and anything bigger (``pyproject.toml``, any ``conftest.py``,
   ``--all-files``, a wide fan-out): fail in about a second with the command
   that runs the suite in chunks of under 60 s each and writes the stamp.

Usage: ``pytest_changed.py [changed files...]`` from the repo root.
"""

from __future__ import annotations

import ast
from collections import defaultdict, deque
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import NamedTuple

import pytest_store

_ROOTS = {
    "tutor": "tutor",
    "tests": "tests",
    "packages/code_runner/code_runner": "code_runner",
}
_TEST_DIRS = ("tests", "tutor/tests", "packages/code_runner/code_runner/tests")
_HARNESS = "packages/code_runner/code_runner/harness/"
_DOTTED = re.compile(r"\b(?:tutor|code_runner|tests)(?:\.\w+)+")
_PYTEST = [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q"]
# Above this share of the test files a subset saves too little to be worth
# the narrowed gate: run the full suite (also under the 60 s cap).
_FULL_SHARE = 0.6
RUN_CMD = ".venv/bin/python scripts/pytest_stamp.py run"
# Above this share of the tests the hook will not run inline: it asks for the
# chunked, stamped run instead (inline would not be sure to fit the 60 s cap).
_INLINE_SHARE = 0.25
# pytest-xdist workers: the sandbox waits (bubblewrap) dominate wall time.
WORKERS = int(os.environ.get("PYTEST_WORKERS", "6"))
# pyproject's addopts carry the full-suite --cov gate; a subset swaps it out.
_SUBSET_OPTS = ["-o", "addopts=-ra --strict-markers --strict-config"]


def _module_name(path: Path) -> str | None:
    """Dotted module name of a repo-relative ``path``, or ``None`` if unmapped."""
    posix = path.as_posix()
    for root, package in _ROOTS.items():
        if posix.startswith(f"{root}/") or posix == f"{root}.py":
            if posix.startswith(_HARNESS):
                return None
            rest = path.relative_to(root).with_suffix("")
            parts = [package, *rest.parts]
            if parts[-1] == "__init__":
                parts.pop()
            return ".".join(parts)
    return None


def _is_test_file(path: Path) -> bool:
    posix = path.as_posix()
    in_dir = any(posix.startswith(f"{d}/") for d in _TEST_DIRS)
    return in_dir and path.name.startswith("test_") and path.suffix == ".py"


def _parents(name: str) -> list[str]:
    parts = name.split(".")
    return [".".join(parts[:i]) for i in range(1, len(parts) + 1)]


def _referenced(tree: ast.AST, source: str, known: set[str]) -> set[str]:
    """Known modules a file imports or names in a dotted string."""
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            found.add(node.module)
            found.update(f"{node.module}.{a.name}" for a in node.names)
    found.update(_DOTTED.findall(source))
    hits: set[str] = set()
    for name in found:
        parts = name.split(".")
        for i in range(len(parts), 0, -1):  # longest known prefix (drops attrs)
            if ".".join(parts[:i]) in known:
                hits.update(_parents(".".join(parts[:i])))
                break
    return hits & known


def _all_python() -> list[Path]:
    return sorted(p for root in _ROOTS for p in Path(root).rglob("*.py"))


def _reverse_graph(files: list[Path]) -> dict[str, set[str]]:
    """Map module -> modules that reference it."""
    names = {f: _module_name(f) for f in files}
    known = {n for n in names.values() if n}
    users: dict[str, set[str]] = defaultdict(set)
    for path, name in names.items():
        if not name:
            continue
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for target in _referenced(tree, source, known):
            if target != name:
                users[target].add(name)
    return users


def _reach(changed: set[str], users: dict[str, set[str]]) -> set[str]:
    seen = set(changed)
    queue = deque(changed)
    while queue:
        for user in users.get(queue.popleft(), ()):
            if user not in seen:
                seen.add(user)
                queue.append(user)
    return seen


def _run(cmd: list[str], env: dict[str, str] | None = None) -> int:
    return subprocess.run(cmd, check=False, env=env).returncode


def say(text: str) -> None:
    """One status line, flushed so it stays ordered with pytest's output."""
    sys.stdout.write(f"pytest-changed: {text}\n")
    sys.stdout.flush()


def _select(changed: list[Path]) -> tuple[set[Path], list[str], bool]:
    """Test files to run, source files to cover, and whether to go full."""
    files = _all_python()
    by_module = {_module_name(f): f for f in files if _module_name(f)}
    users = _reverse_graph(files)
    start: set[str] = set()
    tests: set[Path] = set()
    sources: list[str] = []
    for path in changed:
        if not path.exists() or path.suffix != ".py":
            continue
        if path.name == "conftest.py":
            return set(), [], True
        if path.as_posix().startswith(_HARNESS):
            tests.update(
                f
                for f in files
                if _is_test_file(f) and "code_runner/tests/" in f.as_posix()
            )
        name = _module_name(path)
        if name is None:
            continue
        start.add(name)
        if not _is_test_file(path) and "/tests/" not in f"/{path.as_posix()}":
            sources.append(path.as_posix())
    tests.update(
        f for m in _reach(start, users) if (f := by_module.get(m)) and _is_test_file(f)
    )
    return tests, sources, False


def all_tests() -> list[Path]:
    """Every test file the full suite runs."""
    return [f for f in _all_python() if _is_test_file(f)]


class Plan(NamedTuple):
    """What a change needs: test files, source files to cover, or the full suite."""

    tests: list[Path]
    sources: list[str]
    full: bool


def plan(changed: list[Path]) -> Plan:
    """Narrow ``changed`` to test files + coverage targets; full when unsure."""
    every = all_tests()
    if not changed or any(p.name == "pyproject.toml" for p in changed):
        return Plan(every, [], full=True)
    tests, sources, go_full = _select(changed)
    if go_full or len(tests) >= _FULL_SHARE * len(every):
        return Plan(every, [], full=True)
    return Plan(sorted(tests), sources, full=False)


def pytest_cmd(workers: int) -> list[str]:
    """Subset pytest command: coverage collected, no gate (the caller reports)."""
    xdist = ["-n", str(workers)] if workers > 1 else []
    return [
        *_PYTEST,
        *xdist,
        "--cov=tutor",
        "--cov=code_runner",
        "--cov-branch",
        "--cov-report=",
        *_SUBSET_OPTS,
    ]


def main(argv: list[str]) -> int:
    """Hook: valid stamp passes; a small change runs inline; else say how to stamp."""
    tree = pytest_store.write_tree()
    if pytest_store.covers(tree, argv):
        say("pass stamp valid for the staged tree")
        return 0
    todo = plan([Path(a) for a in argv])
    if todo.full or len(todo.tests) >= _INLINE_SHARE * len(all_tests()):
        say(f"no pass stamp; each call < 60 s, repeat until done: {RUN_CMD}")
        return 1
    if not todo.tests and not todo.sources:
        say("no mapped python changes: nothing to test")
        return 0
    if not todo.tests:
        say(f"no test reaches {', '.join(todo.sources)}")
        return 1
    say(f"{len(todo.tests)} test files, coverage on {len(todo.sources)} source files")
    return run_covered(todo)


def run_covered(todo: Plan) -> int:
    """Run the plan's tests and require 100% on its sources (one process, inline)."""
    with tempfile.TemporaryDirectory(prefix="pytest-changed-") as tmp:
        env = {**os.environ, "COVERAGE_FILE": str(Path(tmp) / ".coverage")}
        code = _run([*pytest_cmd(WORKERS), *map(str, todo.tests)], env)
        if code or not todo.sources:
            return code
        include = ",".join(f"*/{s}" for s in todo.sources)
        report = [sys.executable, "-m", "coverage", "report", f"--include={include}"]
        return _run(
            [*report, "--fail-under=100", "--show-missing", "--skip-covered"], env
        )


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
