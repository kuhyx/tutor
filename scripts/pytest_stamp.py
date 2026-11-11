#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Run the pre-commit test selection in chunks and stamp the staged tree.

Every call is one process that ends well under the 60 s per-action cap, however
loaded the machine is, so the commit hook itself never has to run the suite:

    .venv/bin/python scripts/pytest_stamp.py run  # repeat until "stamp written"
    .venv/bin/python scripts/pytest_stamp.py run --chunk 2  # only chunk 2

The selection is the one ``pytest_changed.py`` makes from the staged python and
pyproject files (the full suite when it cannot narrow). It is split into
chunks; ``run`` starts chunks while the call has time left, saves progress
under the git dir, and when every chunk has passed it combines the coverage
data, requires 100% line and branch coverage (on the changed source files, or
everywhere for the full suite), and writes the pass stamp for ``git write-tree``.
The hook accepts exactly that tree. Any later change to the index invalidates it.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest_changed as sel
import pytest_store as store

_logger = logging.getLogger(__name__)
_CHUNK_FILES = 16  # files per chunk: ~4 s idle; 48 timed out at load 190 (24 cores)
_BUDGET_S = 45.0  # start no chunk that could end past this many seconds
_CHUNK_TIMEOUT_S = 55
_MORE = 75  # exit code: progress saved, call again
_HOOK_FILES = (".py", "pyproject.toml")


def _staged() -> list[str]:
    out = store.git("diff", "--cached", "--name-only", "--diff-filter=ACMR")
    return [f for f in out.splitlines() if f.endswith(_HOOK_FILES)]


def _unstaged() -> list[str]:
    out = store.git("diff", "--name-only")
    return [f for f in out.splitlines() if f.endswith(_HOOK_FILES)]


def _split(tests: list[Path]) -> list[list[str]]:
    """Balanced chunks (largest files first into the lightest chunk)."""
    count = max(1, -(-len(tests) // _CHUNK_FILES))
    bins: list[tuple[int, list[str]]] = [(0, []) for _ in range(count)]
    for path in sorted(tests, key=lambda p: -p.stat().st_size):
        bins.sort(key=lambda b: b[0])
        weight, names = bins[0]
        bins[0] = (weight + path.stat().st_size, [*names, path.as_posix()])
    return [sorted(names) for _, names in sorted(bins, key=lambda b: b[1]) if names]


@dataclass
class State:
    """Progress of one tree's run, saved between calls."""

    files: list[str]
    full: bool
    sources: list[str]
    chunks: list[list[str]]
    done: list[int] = field(default_factory=list)


def _state_file(tree: str) -> Path:
    return store.state_dir() / f"{tree}.state.json"


def _load(tree: str, files: list[str], todo: sel.Plan) -> State:
    """Saved progress for this tree and selection, or a fresh state."""
    path = _state_file(tree)
    if path.is_file():
        saved = State(**json.loads(path.read_text(encoding="utf-8")))
        if saved.files == files and saved.full == todo.full:
            return saved
    return State(files, todo.full, todo.sources, _split(todo.tests))


def _save(tree: str, state: State) -> None:
    _state_file(tree).write_text(json.dumps(asdict(state)), encoding="utf-8")


def _cov_file(tree: str, index: int) -> Path:
    return store.state_dir() / f"{tree}.cov.{index}"


def _run_chunk(tree: str, index: int, names: list[str]) -> bool:
    env = {**os.environ, "COVERAGE_FILE": str(_cov_file(tree, index))}
    cmd = [*sel.pytest_cmd(sel.WORKERS), *names]
    try:
        return (
            subprocess.run(
                cmd, check=False, env=env, timeout=_CHUNK_TIMEOUT_S
            ).returncode
            == 0
        )
    except subprocess.TimeoutExpired:
        _logger.warning("chunk %d timed out", index + 1)
        sel.say(f"chunk {index + 1} passed {_CHUNK_TIMEOUT_S} s: lower _CHUNK_FILES")
        return False


def _coverage_ok(tree: str, sources: list[str]) -> bool:
    """Combine the chunk data and require 100% branch coverage."""
    data = store.state_dir() / f"{tree}.cov"
    parts = sorted(str(p) for p in store.state_dir().glob(f"{tree}.cov.*"))
    base = [sys.executable, "-m", "coverage"]
    subprocess.run(
        [*base, "combine", "--keep", f"--data-file={data}", *parts],
        check=True,
        capture_output=True,
    )
    include = [f"--include={','.join(f'*/{s}' for s in sources)}"] if sources else []
    report = [*base, "report", f"--data-file={data}", *include]
    return (
        subprocess.run(
            [*report, "--fail-under=100", "--show-missing", "--skip-covered"],
            check=False,
        ).returncode
        == 0
    )


def _work(tree: str, state: State, only: int | None, *, full: bool) -> int:
    """Run pending chunks while the call has time left; 0 ok, 1 failed, 75 more."""
    chunks, done = state.chunks, state.done
    pending = [i for i in range(len(chunks)) if i not in done]
    if only is not None:
        pending = [only - 1] if 0 <= only - 1 < len(chunks) else []
    started, longest = time.monotonic(), 0.0
    for index in pending:
        if longest and time.monotonic() - started + 1.5 * longest > _BUDGET_S:
            break
        began = time.monotonic()
        ok = _run_chunk(tree, index, chunks[index])
        took = time.monotonic() - began
        longest = max(longest, took)
        load = os.getloadavg()[0]
        word = "ok" if ok else "FAILED"
        label = f"chunk {index + 1}/{len(chunks)}"
        sel.say(f"{label} {word} in {took:.0f} s (load {load:.0f})")
        if not ok:
            return 1
        done.append(index)
        _save(tree, state)
    left = len(chunks) - len(set(done))
    if left:
        again = f"{sel.RUN_CMD} --full" if full else sel.RUN_CMD
        sel.say(f"{left} chunks left: {again}")
        return _MORE
    return 0


def run(only: int | None, *, full: bool = False) -> int:
    """Run pending chunks within the time budget; stamp the tree when all pass.

    ``full`` runs the whole suite even when nothing python is staged: a tree
    from a dart-only commit has no stamp, and ``pre-commit run --all-files``
    asks for a full one.
    """
    dirty = _unstaged()
    if dirty:
        sel.say(f"unstaged changes to {', '.join(dirty[:5])}: git add them first")
        return 2
    tree, files = store.write_tree(), _staged()
    todo = (
        sel.Plan(sel.all_tests(), [], full=True)
        if full
        else sel.plan([Path(f) for f in files])
    )
    if store.covers(tree, ["*"] if full else files) or not todo.tests:
        sel.say("stamp already valid or nothing to run")
        return 0
    state = _load(tree, files, todo)
    code = _work(tree, state, only, full=full)
    if code or not _coverage_ok(tree, state.sources):
        return code or 1
    info = {"full": state.full, "files": files, "chunks": len(state.chunks)}
    store.write_stamp(tree, info)
    sel.say("stamp written")
    return 0


def main(argv: list[str]) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    runner = sub.add_parser("run", help="run pending chunks, stamp when all pass")
    runner.add_argument("--chunk", type=int, help="run only this chunk (1-based)")
    runner.add_argument(
        "--full", action="store_true", help="the whole suite, nothing staged needed"
    )
    args = parser.parse_args(argv)
    return run(args.chunk, full=args.full)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
