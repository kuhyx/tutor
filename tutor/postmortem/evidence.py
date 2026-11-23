# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""What kuhy did on each problem of a finished unit, measured by code.

Reads leetcode-guard's display files (``history/<slug>.json``,
``attempts.json``) and the coach's ``lc_sessions`` the way ``rework_context``
does: anyone can edit them, so a bad file or row is left out, never raised.
They feed a report and a prompt, never a gate: the trigger (C6) and the
revision row (C7) are the only signed inputs.

One-shot (kuhy, 2026-11-23): no non-Accepted submission before the first
Accepted, and no coach hint (``rungs``) or ``revealed`` on the slug. A solve
is post-theory when its first Accepted comes after the unit's theory was
first done (every module's first signed ``done: true``, the latest of them).
Active minutes only rank effort; most solves have no beats (``None``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import pairwise
from typing import TYPE_CHECKING, Any, Final

from tutor import rework_context as rc
from tutor.curriculum import module_state
from tutor.postmortem import signed

if TYPE_CHECKING:
    from pathlib import Path

ACCEPTED: Final = "Accepted"
GAP_S: Final = 5 * 60  # the guard's ``_attempts.GAP_SECONDS``
MAX_CODE: Final = 1500
_BEAT: Final = 2  # a beat is [unix_seconds, tab]
CODE_WAIT_S: Final = 24 * 3600  # after this, analyse without the missing code


@dataclass(frozen=True)
class Request:
    """A signed C6 row (or the dry-run row): the unit and the solves it claims."""

    unit: str
    subject: str
    modules: tuple[str, ...]
    at: float
    solves: tuple[str, ...]


def parse_request(row: dict[str, Any]) -> Request | None:
    """The row's request; ``None`` when its detail is malformed."""
    d = row.get("detail")
    if not isinstance(d, dict):
        return None
    unit, subject, at = d.get("unit"), d.get("subject"), d.get("at")
    mods, solves = d.get("modules"), d.get("solves")
    strs = (unit, subject)
    if not all(isinstance(s, str) and s for s in strs) or isinstance(at, bool):
        return None
    if not isinstance(at, int | float):
        return None
    if not isinstance(mods, list) or not isinstance(solves, list):
        return None
    if not all(isinstance(x, str) and rc.SLUG.fullmatch(x) for x in [*mods, *solves]):
        return None
    return Request(str(unit), str(subject), tuple(mods), float(at), tuple(solves))


@dataclass
class Solve:
    """One problem's measured story."""

    slug: str
    ac_at: int | None = None
    tries: int = 0  # non-Accepted submissions before the first Accepted
    statuses: list[str] = field(default_factory=list)
    code: str = ""  # the first Accepted's code
    failed_code: str = ""  # the last failing code before it
    minutes: int | None = None
    hints: int = 0
    revealed: bool = False
    post: bool = False

    @property
    def one_shot(self) -> bool:
        """No miss, no hint, no reveal before the first Accepted."""
        return self.ac_at is not None and not (
            self.tries or self.hints or self.revealed
        )

    def row(self) -> dict[str, Any]:
        """The report's measured fields."""
        return {
            "slug": self.slug,
            "tries": self.tries,
            "minutes": self.minutes,
            "hints": self.hints,
            "revealed": self.revealed,
            "one_shot": self.one_shot,
            "phase": "post" if self.post else "pre",
            "ac_at": self.ac_at,
        }


def _num(value: object) -> int:
    return int(value) if isinstance(value, int | float) else 0


def _subs(slug: str) -> list[dict[str, Any]]:
    raw = rc.read_file(rc.guard_dir() / "history" / f"{slug}.json")
    rows = rc.dict_rows(raw.get("submissions") if isinstance(raw, dict) else None)
    return sorted(rows, key=lambda r: _num(r.get("timestamp")))


def has_code(slug: str) -> bool:
    """Whether the mirror holds the code of an Accepted submission of ``slug``."""
    return any(
        r.get("status") == ACCEPTED and isinstance(r.get("code"), str) and r["code"]
        for r in _subs(slug)
    )


def _beats(slug: str, until: int | None) -> list[int]:
    raw = rc.read_file(rc.guard_dir() / "attempts.json")
    recs = rc.dict_rows(raw.get("records") if isinstance(raw, dict) else None)
    found = [
        _num(b[0])
        for rec in recs
        if rec.get("slug") == slug
        for b in rec.get("beats") or []
        if isinstance(b, list) and len(b) == _BEAT
    ]
    return sorted(t for t in found if t and (until is None or t <= until))


def minutes(beats: list[int], end: int | None) -> int | None:
    """Active minutes: gaps of at most :data:`GAP_S`; ``None`` with no beat."""
    if not beats:
        return None
    times = [*beats, end] if end is not None and end >= beats[-1] else beats
    return round(sum(b - a for a, b in pairwise(times) if b - a <= GAP_S) / 60)


def _coach(slug: str) -> tuple[int, bool]:
    """(hint rungs climbed, revealed) over every coach session on ``slug``."""
    hints, revealed = 0, False
    for state in rc.sessions_of(slug):
        rungs = state.get("rungs")
        hints += len(rungs) if isinstance(rungs, list) else 0
        revealed = revealed or state.get("revealed") is True
    return hints, revealed


def _cap(code: object) -> str:
    text = code if isinstance(code, str) else ""
    return text if len(text) <= MAX_CODE else text[:MAX_CODE] + "\n[...]"


def solve_of(slug: str, done_at: float | None) -> Solve:
    """``slug`` measured; ``done_at`` (seconds) splits pre- from post-theory."""
    subs = _subs(slug)
    first = next((i for i, r in enumerate(subs) if r.get("status") == ACCEPTED), None)
    found = Solve(slug)
    before = subs if first is None else subs[:first]
    found.tries = len(before)
    found.statuses = [str(r.get("status")) for r in subs[: (first or 0) + 1]]
    if first is not None:
        found.ac_at = _num(subs[first].get("timestamp")) or None
        found.code = _cap(subs[first].get("code"))
    if before:
        found.failed_code = _cap(before[-1].get("code"))
    found.minutes = minutes(_beats(slug, found.ac_at), found.ac_at)
    found.hints, found.revealed = _coach(slug)
    found.post = bool(done_at and found.ac_at and found.ac_at > done_at)
    return found


def theory_done_at(root: Path, subject: str, modules: tuple[str, ...]) -> float | None:
    """When the unit's theory was first done: the latest module's first ``done``."""
    rows = signed.verified_rows(root / "module_state.json", module_state.KIND)
    firsts: dict[str, float] = {}
    for row in rows or []:
        d = row.get("detail") or {}
        mod, at = d.get("module"), d.get("at")
        if d.get("subject") != subject or d.get("done") is not True:
            continue
        if mod in modules and isinstance(at, int | float) and mod not in firsts:
            firsts[str(mod)] = float(at)
    if not modules or set(firsts) != set(modules):
        return None
    return max(firsts.values())
