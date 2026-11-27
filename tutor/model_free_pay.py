# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The run and pay of the model-free modes: the drill and read mode.

A run is a tutor session (``<prefix>-<YYYYmmdd-HHMMSS>-<4hex>``, one per
local day, a new one after a restart) with its own :class:`EngagementClock`.
Shown -> answered is a learner gap on it, whatever the answer; released
minutes go through ``unit_credit.credit_units`` (daily cap; the row kind
follows the subject, ``ledger_pay.kind_for``). An answer under
:data:`MIN_PICK_SECONDS` earns nothing. A run logs to
``<data>/<prefix>/<run>.jsonl``, not ``sessions/`` (History reads that).
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import time
from typing import TYPE_CHECKING, Any, Final
import uuid

from tutor import credit, unit_credit
from tutor.clock import EngagementClock

if TYPE_CHECKING:
    from pathlib import Path

    from tutor import ledger_pay

MIN_PICK_SECONDS: Final = 3.0  # a faster pick is a guess: it earns nothing
# The clock's filler test is for typed replies; a pick is never filler.
_PICK_TEXT: Final = "multiple-choice pick"


@dataclass
class Run:
    """One model-free session: its id, local day and clock."""

    session_id: str
    day: str
    clock: EngagementClock


class Runs:
    """One mode's runs (``prefix``: ``drill`` or ``read``) under data dir ``root``."""

    def __init__(self, root: Path, prefix: str) -> None:
        """No run until the first :meth:`run_for`."""
        self.dir, self.prefix = root / prefix, prefix
        self.current: Run | None = None

    def run_for(self, at: float) -> Run:
        """Today's run (a new session id each local day, and after a restart)."""
        day = credit.local_day(at)[0]
        if self.current is None or self.current.day != day:
            stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(at))
            sid = f"{self.prefix}-{stamp}-{uuid.uuid4().hex[:4]}"
            self.current = Run(sid, day, EngagementClock(at))
        return self.current

    def today(self, at: float) -> dict[str, int]:
        """This run's active minutes today and the ledger's credited minutes."""
        run = self.current
        today = run is not None and run.day == credit.local_day(at)[0]
        active = run.clock.active_seconds if run is not None and today else 0.0
        paid = unit_credit.ledger_minutes_today(at)
        return {"active_min": int(active // 60), "credited_min": paid}

    def log(self, run: Run, event: dict[str, Any]) -> None:
        """Append ``event`` to the run's ``<prefix>/<run>.jsonl``."""
        path = self.dir / f"{run.session_id}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps({"logged_at": time.time(), **event}, ensure_ascii=False)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def accrue(
        self, run: Run, span: tuple[float, float], taught: ledger_pay.Taught
    ) -> list[dict[str, Any]]:
        """Shown -> answered (``span``) is a learner gap; credit what it releases.

        Every minute released ends at this answer, so each row carries
        ``taught`` (the answered card's subject and module). The rows are
        logged and returned.
        """
        (shown, at), clock = span, run.clock
        clock.tutor_message(shown)
        clock.user_reply(at, _PICK_TEXT, low_effort=at - shown < MIN_PICK_SECONDS)
        clock.tutor_message(at)  # a zero "tutor gap": nothing accrues after it
        units = clock.ready_blocks()
        subject = taught.get("subject")
        rows = (
            unit_credit.credit_units(
                units, run.session_id, now=at, subject=subject, taught=taught
            )
            if units
            else []
        )
        for row in rows:
            self.log(run, {"type": "credit", **row})
        return rows


def credited(rows: list[dict[str, Any]]) -> bool:
    """Whether any of ``rows`` recorded a minute."""
    return any(r["recorded"] and r["minutes"] for r in rows)
