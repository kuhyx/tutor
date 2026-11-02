# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""An in-memory stand-in for the ``focus_project`` contract API (tests only)."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import date


@dataclass(frozen=True)
class FakeProject:
    """The contract's Project fields the worker reads."""

    id: str
    name: str
    start: date
    end: date
    replaces: tuple[str, ...]
    daily_minutes: int
    unlock_minutes: int
    subjects: tuple[str, ...] = ()
    site_patterns: tuple[str, ...] = ()
    ended_on: date | None = None
    created_ms: int = 0

    @property
    def last_day(self) -> date:
        """The early-end day if set, else ``end``."""
        return self.ended_on or self.end


@dataclass
class FakeFp:
    """Records every call; ``create_project`` refuses overlaps like the real one."""

    projects: list[FakeProject] = field(default_factory=list)
    activity: list[dict[str, Any]] = field(default_factory=list)
    minutes: int = 0
    boom: Exception | None = None
    updated_on: date | None = None

    def _check(self) -> None:
        if self.boom is not None:
            raise self.boom

    def list_projects(self) -> list[FakeProject]:
        """Every project, file order."""
        self._check()
        return list(self.projects)

    def active(self, day: date) -> FakeProject | None:
        """The project covering ``day``."""
        self._check()
        return next((p for p in self.projects if p.start <= day <= p.last_day), None)

    def minutes_for(self, day: date) -> int:
        """The canned minutes."""
        return self.minutes

    def status(self, day: date) -> dict[str, Any]:
        """The contract's status dict."""
        found = self.active(day)
        if found is None:
            return {
                "project": None,
                "name": None,
                "minutes": 0,
                "daily_minutes": None,
                "unlock_minutes": None,
                "ends": None,
                "replaces": [],
            }
        return {
            "project": found.id,
            "name": found.name,
            "minutes": self.minutes,
            "daily_minutes": found.daily_minutes,
            "unlock_minutes": found.unlock_minutes,
            "ends": found.last_day.isoformat(),
            "replaces": list(found.replaces),
        }

    def record_activity(self, source: str, kind: str, **kw: Any) -> None:
        """Remember the call."""
        self._check()
        self.activity.append({"source": source, "kind": kind, **kw})

    def create_project(self, project_id: str, **kw: Any) -> FakeProject:
        """Add a project; ValueError on a duplicate id or an overlap."""
        self._check()
        tupled = {k: tuple(v) for k, v in kw.items() if isinstance(v, list)}
        new = FakeProject(project_id, **{**kw, **tupled})
        for other in self.projects:
            if new.start <= other.last_day and other.start <= new.last_day:
                msg = f"project overlaps {other.id!r}"
                raise ValueError(msg)
        self.projects.append(new)
        return new

    def end_project(self, project_id: str, day: date) -> FakeProject:
        """End early; KeyError when unknown."""
        self._check()
        for i, found in enumerate(self.projects):
            if found.id == project_id:
                self.projects[i] = replace(found, ended_on=day)
                return self.projects[i]
        raise KeyError(project_id)

    def update_project(
        self, project_id: str, today: date | None = None, **kw: Any
    ) -> FakeProject:
        """Edit fields; KeyError when unknown, ValueError on an overlap."""
        self._check()
        self.updated_on = today
        tupled = {k: tuple(v) for k, v in kw.items() if isinstance(v, list)}
        for i, found in enumerate(self.projects):
            if found.id != project_id:
                continue
            new = replace(found, **{**kw, **tupled})
            for other in self.projects:
                if other is not found and (
                    new.start <= other.last_day and other.start <= new.last_day
                ):
                    msg = f"project overlaps {other.id!r}"
                    raise ValueError(msg)
            self.projects[i] = new
            return new
        raise KeyError(project_id)
