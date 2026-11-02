# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Pre-built mock papers waiting under ``<data>/mocks_ready/`` (oldest first)."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from tutor.store import data_dir

if TYPE_CHECKING:
    from pathlib import Path

type Json = Any
_logger = logging.getLogger(__name__)


def _dir() -> Path:
    path = data_dir() / "mocks_ready"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _files() -> list[Path]:
    return sorted(_dir().glob("*.json"), key=lambda p: (p.stat().st_mtime, p.name))


def count() -> int:
    """How many papers are waiting."""
    return len(_files())


def stock(mock: dict[str, Json]) -> None:
    """Add a finished paper to the pool (atomic write)."""
    target = _dir() / f"{mock['id']}.json"
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(mock), encoding="utf-8")
    tmp.replace(target)


def _read(path: Path) -> dict[str, Json] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError, ValueError:
        _logger.warning("unreadable pre-built mock %s", path.name)
        return None
    if not isinstance(data, dict):
        _logger.warning("pre-built mock %s is not an object", path.name)
        return None
    return data


def take() -> dict[str, Json] | None:
    """Remove and return the oldest paper; an unreadable file is dropped."""
    for path in _files():
        data = _read(path)
        path.unlink(missing_ok=True)
        if data is not None:
            return data
    return None


def used() -> tuple[set[str], set[str]]:
    """(MCQ snippets, SQL drill ids) already in the pool, to avoid repeats."""
    codes: set[str] = set()
    drills: set[str] = set()
    for path in _files():
        data = _read(path)
        if data is None:
            continue
        codes.update(t["code"] for t in data["tasks"] if t.get("code"))
        drills.update(t["drill"] for t in data["private"] if t.get("drill"))
    return codes, drills
