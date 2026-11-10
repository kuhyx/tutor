#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Pass-stamp storage for the pre-commit pytest gate.

A stamp says "the staged tree with this ``git write-tree`` hash passed the
tests and the 100% branch gate". It lives under the git dir (worktree-aware,
never committed). Any change to the staged tree changes the hash, so a stamp
can never outlive the content it vouches for.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess

_GIT = "/usr/bin/git"


def git(*args: str) -> str:
    """Stdout of a git command, stripped; raises ``CalledProcessError`` on failure."""
    done = subprocess.run([_GIT, *args], check=True, capture_output=True, text=True)
    return done.stdout.strip()


def write_tree() -> str:
    """Hash of the tree the next commit would record (the index)."""
    return git("write-tree")


def state_dir() -> Path:
    """``<git-dir>/pytest-stamp``: per worktree, created on demand."""
    path = Path(git("rev-parse", "--git-path", "pytest-stamp")).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def stamp_file(tree: str) -> Path:
    """Where the pass stamp of ``tree`` lives."""
    return state_dir() / f"{tree}.stamp.json"


def read_stamp(tree: str) -> dict[str, object] | None:
    """The stamp for ``tree``, or ``None`` if the tree never passed."""
    path = stamp_file(tree)
    if not path.is_file():
        return None
    data: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
    return data if data.get("tree") == tree else None


def write_stamp(tree: str, data: dict[str, object]) -> None:
    """Record that ``tree`` passed; drops every other tree's stamp and state."""
    for old in state_dir().iterdir():
        if not old.name.startswith(tree):
            old.unlink(missing_ok=True)
    stamp_file(tree).write_text(
        json.dumps({"tree": tree, **data}, indent=2), encoding="utf-8"
    )


def covers(tree: str, changed: list[str]) -> bool:
    """True if ``tree`` passed a run that covered every file in ``changed``."""
    stamp = read_stamp(tree)
    if stamp is None:
        return False
    if stamp.get("full"):
        return True
    files = stamp.get("files")
    return isinstance(files, list) and set(changed) <= set(files)
