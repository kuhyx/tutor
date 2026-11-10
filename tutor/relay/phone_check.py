# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The phone-prep report an active interview project's ``phone:*`` milestone reads.

Only this worker can count due cards and read the phone's RTDB presence, so it
appends ``phone_check`` evidence ``{plan, due, seen_ms}`` through
``focus_project.record_evidence`` (the rule that judges it, 24 h freshness
included, lives in ``focus_project.checks``) and then runs ``run_checks`` so a
passing verdict is latched. It fails closed: an unreadable presence is
``seen_ms`` 0 with a warning, which makes the check fail rather than pass.

Triggers: every ``INTERVAL_S``, and soon after any served request
(:meth:`PhoneCheck.poke`, at most one run per ``GAP_S``). Appends are limited
to one per ``APPEND_EVERY_S`` unless the verdict inputs changed: ``seen_ms``
moves on every phone ping, so only "plan, any card due, phone seen within 24 h"
count as a change.
"""

from __future__ import annotations

import asyncio
import contextlib
from datetime import date
import logging
from typing import TYPE_CHECKING, Any, Final

from tutor import credit, focus_hook
from tutor.curriculum import rules
from tutor.curriculum.errors import RequestError
from tutor.curriculum.no_card import due_in_subject
from tutor.relay import plan
from tutor.relay.focus_common import naive_local
from tutor.relay.rtdb import RtdbError

if TYPE_CHECKING:
    from tutor.focus_hook import ProjectLike
    from tutor.relay.context import Wiring

INTERVAL_S: Final = 300.0
GAP_S: Final = 60.0
APPEND_EVERY_S: Final = 1800.0
DAY_MS: Final = 24 * 3600 * 1000
_logger = logging.getLogger(__name__)
Key = tuple[bool, bool, bool]


class PhoneCheck:
    """Reports phone readiness for the active interview project."""

    def __init__(self, wiring: Wiring) -> None:
        """Bind the worker's collaborators; nothing has been reported yet."""
        self.w = wiring
        self._poked = asyncio.Event()
        self._last: tuple[str, float, Key] | None = None  # project, when, inputs

    def poke(self) -> None:
        """Ask for a run soon (a request was served)."""
        self._poked.set()

    async def run(self) -> None:
        """Tick on every poke and at least every ``INTERVAL_S``, forever."""
        while True:
            self._poked.clear()
            await self.tick()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._poked.wait(), INTERVAL_S)
            await asyncio.sleep(GAP_S)

    async def tick(self) -> None:
        """One report if due; a failure is logged and never raised."""
        try:
            await self._tick()
        except focus_hook.BROKEN:
            _logger.exception("phone check failed")

    async def _tick(self) -> None:
        fp = focus_hook.load_fp()
        if fp is None or not hasattr(fp, "run_checks"):
            return
        now = self.w.now()
        project = fp.active(date.fromisoformat(credit.local_day(now)[0]))
        if project is None or getattr(project, "kind", "focus") != "interview":
            return
        stamp = naive_local(now)
        now_ms = int(now * 1000)
        seen_ms = await self._seen_ms()
        has_plan = plan.has_steps(credit.local_day(now)[0])
        due = self._due(project, now_ms)
        report = {"plan": has_plan, "due": due, "seen_ms": seen_ms}
        key: Key = (has_plan, due > 0, now_ms - seen_ms <= DAY_MS)
        last = self._last
        if (
            last is None
            or last[0] != project.id
            or last[2] != key
            or (now - last[1] >= APPEND_EVERY_S)
        ):
            fp.record_evidence(project.id, "phone", "phone_check", report, now=stamp)
            self._last = (project.id, now, key)
        fp.run_checks(project.id, now=stamp)

    async def _seen_ms(self) -> int:
        """The newest ``seen`` of an android client; 0 (and a warning) if none."""
        try:
            clients: Any = await self.w.rtdb.get("presence/clients")
        except RtdbError as exc:
            _logger.warning("phone check: presence unreadable (%s); seen_ms 0", exc)
            return 0
        rows = clients.values() if isinstance(clients, dict) else []
        seen = [
            c["seen"]
            for c in rows
            if isinstance(c, dict)
            and c.get("platform") == "android"
            and isinstance(c.get("seen"), int)
            and not isinstance(c["seen"], bool)
        ]
        if not seen:
            _logger.warning("phone check: no phone in presence/clients; seen_ms 0")
        return max(seen, default=0)

    def _due(self, project: ProjectLike, now_ms: int) -> int:
        """Due reviews over the project's subjects, as ``plan_auto`` counts them."""
        if not project.subjects:
            return 0
        cur = self.w.engine.ctx
        fold = cur.fold()
        total = 0
        for name in project.subjects:
            try:
                found, cards = cur.subjects.plan(name), cur.subjects.cards(name)
            except RequestError:  # an id that is not a subject
                _logger.warning("phone check: %r is not a subject", name)
                continue
            if found is not None:
                total += due_in_subject(rules.View(name, found, cards), fold, now_ms)
        return total
