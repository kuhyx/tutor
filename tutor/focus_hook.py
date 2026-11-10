# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Tutor minutes count as focus work when the subject is on the active project.

``focus_project`` is optional and lives outside this repo: it is imported
lazily (:func:`load_fp`), typed here by the slice of its contract the worker
uses, and nothing here may ever break a credit: every failure is logged and
swallowed (the ledger row is already written when this runs).
"""

from __future__ import annotations

from datetime import date, datetime
import importlib
import importlib.util
import logging
from typing import TYPE_CHECKING, Any, Protocol, cast

from tutor import credit

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

_logger = logging.getLogger(__name__)
# What a hook may hit when the optional package is broken or half-written.
BROKEN = (
    ArithmeticError,
    AttributeError,
    ImportError,
    LookupError,
    OSError,
    RuntimeError,
    SyntaxError,
    TypeError,
    ValueError,
)


class ProjectLike(Protocol):
    """The fields of ``focus_project.Project`` the worker reads."""

    id: str
    name: str
    start: date
    end: date
    last_day: date
    replaces: Sequence[str]
    daily_minutes: int
    unlock_minutes: int
    subjects: Sequence[str]
    site_patterns: Sequence[str]
    work_url: str
    created_ms: int
    # focus_project 0.9.0; ``getattr(project, "kind", "focus")`` reads an older one.
    kind: str
    test_at: datetime | None
    invite_url: str
    trips: Sequence[TripLike]
    weekend_answers: Sequence[tuple[date, bool]]


class TripLike(Protocol):
    """``focus_project.Trip``: an inclusive away range."""

    start: date
    end: date


class MilestoneLike(Protocol):
    """``focus_project.Milestone``."""

    @property
    def red(self) -> bool:
        """Past due and not done."""
        ...

    def to_dict(self) -> dict[str, Any]:
        """The status row ``{id, due, state}``."""
        ...


class UpdateLike(Protocol):
    """``focus_project.Update``: the edited project, and when it takes hold."""

    effective_from: date


class FocusApi(Protocol):
    """``import focus_project as fp``: the contract functions used here."""

    def active(self, day: date) -> ProjectLike | None:
        """The project active on ``day``."""
        ...

    def list_projects(self) -> list[ProjectLike]:
        """Every project."""
        ...

    def minutes_for(self, day: date) -> int:
        """Focus minutes of ``day``."""
        ...

    def status(self, day: date) -> dict[str, Any]:
        """Progress of ``day``'s project (``project`` None if none)."""
        ...

    def record_activity(
        self, source: str, kind: str, ts: float | None = None, dev: str = "pc"
    ) -> None:
        """Append one activity event."""
        ...

    def create_project(self, project_id: str, **fields: object) -> ProjectLike:
        """Add a project; ``ValueError`` on bad input or an overlap."""
        ...

    def apply_update(
        self, project_id: str, *, today: date | None = None, **fields: object
    ) -> UpdateLike:
        """Edit a project; ``ValueError`` / ``KeyError`` if impossible."""
        ...

    def end_project(self, project_id: str, day: date) -> ProjectLike:
        """End early; ``ValueError`` / ``KeyError`` if impossible."""
        ...

    # -- interview projects (focus_project 0.9.0) --------------------------------
    Trip: Callable[[date, date], TripLike]

    def milestones(
        self, project: ProjectLike, now: datetime
    ) -> Sequence[MilestoneLike]:
        """The project's generated milestones at ``now`` (naive local)."""
        ...

    def record_evidence(
        self,
        project_id: str,
        milestone: str,
        kind: str,
        value: object = None,
        **kw: object,
    ) -> object:
        """Append evidence (``file=Path``, ``now=datetime`` by keyword); ValueError."""
        ...

    def add_trip(
        self, project_id: str, start: date, end: date, *, now: datetime | None = None
    ) -> object:
        """Announce a trip; ``ValueError`` if it would loosen an old one."""
        ...

    def answer_weekend(
        self,
        project_id: str,
        saturday: date,
        *,
        trip: bool,
        now: datetime | None = None,
    ) -> object:
        """Answer a weekend's trip question; a True never flips back."""
        ...

    def run_checks(
        self, project_id: str, *, now: datetime | None = None
    ) -> dict[str, bool | None]:
        """Run the auto checks of the open phone milestones and latch them."""
        ...


def load_fp() -> FocusApi | None:
    """The ``focus_project`` package, or ``None`` when it is not installed."""
    if importlib.util.find_spec("focus_project") is None:
        return None
    return cast("FocusApi", importlib.import_module("focus_project"))


def heartbeat(subject: str | None, now: float, ts: float | None) -> None:
    """Beat at ``ts`` (``None``: the clock) if ``subject`` is on the project.

    The project is the one active on ``now``'s local day.
    """
    if not subject:
        return
    try:
        fp = load_fp()
        if fp is None:
            return
        project = fp.active(date.fromisoformat(credit.local_day(now)[0]))
        if project is not None and subject in project.subjects:
            fp.record_activity("tutor", "heartbeat", ts=ts)
    except BROKEN:
        _logger.exception("focus heartbeat for %r skipped", subject)
