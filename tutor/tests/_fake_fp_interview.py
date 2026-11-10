# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The interview half of the ``focus_project`` 0.9 contract, in memory (tests only)."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any

from tutor.tests._fake_fp import FakeFp, FakeProject

if TYPE_CHECKING:
    from datetime import date, datetime


@dataclass(frozen=True)
class FakeTrip:
    """``focus_project.Trip``."""

    start: date
    end: date
    entered_ms: int = 0


@dataclass(frozen=True)
class FakeMilestone:
    """``focus_project.Milestone``: ``to_dict`` is the status row."""

    id: str
    due: datetime
    state: str

    @property
    def red(self) -> bool:
        return self.state in {"missed", "unknown"}

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "due": self.due.isoformat(), "state": self.state}


@dataclass
class FakeInterviewFp(FakeFp):
    """Records the interview calls; ``refuse`` makes every mutator raise it."""

    Trip = FakeTrip  # fp.Trip(start, end)
    rows: list[FakeMilestone] = field(default_factory=list)
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    refuse: Exception | None = None
    milestones_error: Exception | None = None
    status_extra: dict[str, Any] = field(default_factory=dict)  # e.g. daily_minutes

    def status(self, day: date) -> dict[str, Any]:
        return {**super().status(day), **self.status_extra}

    def _note(self, name: str, **kw: Any) -> None:
        self._check()
        self.calls.append((name, kw))
        if self.refuse is not None:
            raise self.refuse

    def create_project(self, project_id: str, **kw: Any) -> FakeProject:
        """Normalise like the real one: answers become sorted pairs."""
        answers = kw.pop("weekend_answers", None) or {}
        trips = tuple(kw.pop("trips", None) or ())
        made = super().create_project(project_id, **kw)
        pairs = tuple(sorted(answers.items()))
        self.projects[-1] = replace(made, trips=trips, weekend_answers=pairs)
        return self.projects[-1]

    def milestones(self, project: FakeProject, now: datetime) -> list[FakeMilestone]:
        self._check()
        if self.milestones_error is not None:
            raise self.milestones_error
        self.calls.append(("milestones", {"project": project.id, "now": now}))
        return list(self.rows)

    def record_evidence(
        self,
        project_id: str,
        milestone: str,
        kind: str,
        value: object = None,
        **kw: Any,
    ) -> None:
        file = kw.get("file")
        seen = None if file is None else (file.name, file.read_bytes())
        self._note(
            "record_evidence",
            project=project_id,
            milestone=milestone,
            kind=kind,
            value=value,
            file=seen,
            now=kw.get("now"),
        )

    def add_trip(self, project_id: str, start: date, end: date, **kw: Any) -> None:
        self._note("add_trip", project=project_id, start=start, end=end, **kw)
        for i, found in enumerate(self.projects):
            if found.id == project_id:
                trip = FakeTrip(start, end)
                self.projects[i] = replace(found, trips=(*found.trips, trip))

    def answer_weekend(
        self, project_id: str, saturday: date, *, trip: bool, **kw: Any
    ) -> None:
        self._note(
            "answer_weekend", project=project_id, saturday=saturday, trip=trip, **kw
        )
        for i, found in enumerate(self.projects):
            if found.id == project_id:
                pairs = {**dict(found.weekend_answers), saturday: trip}
                self.projects[i] = replace(
                    found, weekend_answers=tuple(sorted(pairs.items()))
                )

    def run_checks(self, project_id: str, **kw: Any) -> dict[str, bool | None]:
        self._note("run_checks", project=project_id, **kw)
        return {}
