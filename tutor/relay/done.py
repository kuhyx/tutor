# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The done-map: every finished request's result, kept 30 days.

``requests_done.jsonl`` in the data dir, one ``{"rid","at","dev","kind",
"result"}`` per line. A rid found here is answered by re-PUTting its result
and is never run again (no second model call, no second credit), even after
RTDB's copy was garbage-collected or a crash lost the result PUT.
"""

from __future__ import annotations

import json
import logging
import os
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from pathlib import Path

KEEP_S: Final = 30 * 24 * 3600.0
_logger = logging.getLogger(__name__)


class DoneMap:
    """rid -> result, appended on commit, pruned to :data:`KEEP_S` on load."""

    def __init__(self, path: Path, now: float) -> None:
        """Load ``path`` and drop rows older than 30 days (rewriting the file)."""
        self.path = path
        self._rows: dict[str, dict[str, Any]] = {}
        kept: list[str] = []
        stale = False
        lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
        for line in lines:
            try:
                row = json.loads(line)
                rid, at = str(row["rid"]), float(row["at"])
            except (ValueError, KeyError, TypeError) as err:
                _logger.warning("done-map line skipped: %s", err)
                stale = True
                continue
            if now - at > KEEP_S:
                stale = True
                continue
            self._rows[rid] = row
            kept.append(line)
        if stale:
            self._rewrite(kept)

    def _rewrite(self, lines: list[str]) -> None:
        tmp = self.path.with_name(f".{self.path.name}.tmp")
        tmp.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
        tmp.replace(self.path)

    def get(self, rid: str) -> dict[str, Any] | None:
        """The recorded row of ``rid``, or ``None``."""
        return self._rows.get(rid)

    def dev_of(self, rid: str) -> str | None:
        """Which device sent ``rid`` (for the projection's learner bubbles)."""
        row = self._rows.get(rid)
        return str(row["dev"]) if row and row.get("dev") else None

    def add(
        self, rid: str, at: float, dev: str, kind: str, result: dict[str, Any]
    ) -> None:
        """Record ``rid`` as done (appended and fsynced before the result PUT)."""
        row = {"rid": rid, "at": at, "dev": dev, "kind": kind, "result": result}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self._rows[rid] = row
