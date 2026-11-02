# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""One JSON file per mock under ``<data>/mocks/``; keys stay server-side."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, Final

from tutor.relay.errors import RequestError
from tutor.store import data_dir

if TYPE_CHECKING:
    from pathlib import Path

type Json = Any
_logger = logging.getLogger(__name__)
KEEP: Final = 20


def _dir() -> Path:
    path = data_dir() / "mocks"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save(mock: dict[str, Json]) -> None:
    """Write ``mock`` atomically; only the newest ``KEEP`` mocks are kept."""
    target = _dir() / f"{mock['id']}.json"
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(mock), encoding="utf-8")
    tmp.replace(target)
    old = sorted(_dir().glob("*.json"), key=lambda p: p.stat().st_mtime)[:-KEEP]
    for path in old:
        path.unlink(missing_ok=True)


def load(mock_id: str) -> dict[str, Json]:
    """The stored mock, or ``bad_request`` for an unknown id."""
    path = _dir() / f"{mock_id}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError, ValueError:
        msg = f"unknown mock {mock_id!r}"
        raise RequestError(msg, code="bad_request") from None
    if not isinstance(data, dict):
        msg = f"unknown mock {mock_id!r}"
        raise RequestError(msg, code="bad_request")
    return data


def seen_drills(limit: int = 6) -> set[str]:
    """SQL drill ids used by the newest mocks (to avoid repeats)."""
    paths = sorted(_dir().glob("*.json"), key=lambda p: p.stat().st_mtime)[-limit:]
    out: set[str] = set()
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except OSError, ValueError:
            _logger.warning("unreadable mock file %s skipped", path.name)
            continue
        private = data.get("private", []) if isinstance(data, dict) else []
        out.update(t["drill"] for t in private if t.get("drill"))
    return out
