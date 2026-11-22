# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""C3: which modules of the gated LeetCode subjects the tutor may teach now.

leetcode-guard writes one signed row to ``theory_phase.json``
(``DOCS-contract-theory-phase.md``); ``detail.teachable`` lists the
``(subject, module)`` pairs of the current unit while the guard is in
THEORY. A module of a :data:`GATED` subject not in that list is never
taught and never marked taught. Fail closed: a missing, unreadable, unsigned,
foreign or malformed file means nothing is teachable, never raised, and
logged as ONE warning per failure: the server reads the file on every plan
publish, so the same failure is not logged again until a read succeeds or
the failure changes. Ungated subjects never read the file.

The path resolves at call time: ``TUTOR_THEORY_PHASE`` moves it (the tests
point it into ``tmp_path``), else it is the guard's data dir under ``HOME``.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Final, NamedTuple

import earned_time

from tutor.ledger_io import default_paths

if TYPE_CHECKING:
    from collections.abc import Iterable

GATED: Final = frozenset(
    {
        "leetcode-easy-algorithms-in-typescript",
        "javascript-and-pandas-for-leetcode-easy",
    }
)
KIND: Final = "theory_phase"
PHASES: Final = frozenset({"theory", "solve", "none"})
_PAIR: Final = 2
_logger = logging.getLogger(__name__)
# The failure last warned about ("" after a good read): one line per failure.
_last_failure = [""]

type Pairs = frozenset[tuple[str, str]]


class Grant(NamedTuple):
    """A trusted row: the unit the guard teaches and the pairs it lists."""

    unit: str  # "" when the row names none
    pairs: Pairs


def phase_path() -> Path:
    """Where the guard writes the row (``TUTOR_THEORY_PHASE`` overrides)."""
    found = os.environ.get("TUTOR_THEORY_PHASE")
    if found:
        return Path(found)
    return Path.home() / ".local/share/leetcode_guard/theory_phase.json"


def _grant(row: object, key: bytes) -> Grant | None:
    """The row's grant; ``None`` when it is not a signed, well-formed C3 row."""
    if not isinstance(row, dict) or row.get("kind") != KIND:
        return None
    detail = row.get("detail")
    if not key or not earned_time.verified(row, key) or not isinstance(detail, dict):
        return None
    raw = detail.get("teachable")
    if detail.get("phase") not in PHASES or not isinstance(raw, list):
        return None
    if not all(
        isinstance(p, list) and len(p) == _PAIR and all(isinstance(x, str) for x in p)
        for p in raw
    ):
        return None
    pairs = frozenset((p[0], p[1]) for p in raw)
    # Only THEORY grants anything: a SOLVE / none row listing modules is a
    # contradiction, read as malformed ("teach nothing", warned).
    if detail["phase"] != "theory" and pairs:
        return None
    unit = detail.get("unit")
    return Grant(unit if isinstance(unit, str) else "", pairs)


def teachable() -> Pairs:
    """The guard's signed ``teachable`` pairs; empty on any failure (one warning)."""
    found = current()
    return found.pairs if found else frozenset()


def current() -> Grant | None:
    """The guard's signed grant; ``None`` on any failure (one warning)."""
    path = phase_path()
    try:
        row = json.loads(path.read_text(encoding="utf-8"))
        key = default_paths().key_file.read_bytes().strip()
        # TypeError: compare_digest refuses a non-ASCII ``hmac`` string.
        found = _grant(row, key)
    except (OSError, ValueError, TypeError) as exc:
        failure = f"theory phase {path} unreadable, nothing teachable: {exc}"
        if _is_new(failure):
            _logger.warning("%s", failure)
        return None
    if found is None:
        failure = f"theory phase {path} not a signed C3 row, nothing teachable"
        if _is_new(failure):
            _logger.warning("%s", failure)
        return None
    _last_failure[0] = ""
    return found


def _is_new(failure: str) -> bool:
    """Whether ``failure`` is not the one last warned about (it is, from now)."""
    new = failure != _last_failure[0]
    _last_failure[0] = failure
    return new


def forget_failure() -> None:
    """Warn about the next failure even if it repeats the last (tests)."""
    _last_failure[0] = ""


def refused(subject: str, modules: Iterable[str]) -> frozenset[str]:
    """The ``modules`` of ``subject`` the tutor must not teach now.

    Ungated subject, or no modules asked about: none, and the file is not read.
    """
    asked = list(modules)
    if subject not in GATED or not asked:
        return frozenset()
    allowed = teachable()
    return frozenset(m for m in asked if (subject, m) not in allowed)


def overlay(subject: str, plan: object) -> object:
    """The published ``plan`` with ``teachable`` on every module of a gated subject.

    Display only, for the plan screen's lock glyph (C4); ``plan.json`` itself
    never carries it. Ungated subjects and a missing plan pass through as is.
    """
    if subject not in GATED or not isinstance(plan, dict):
        return plan
    modules = plan.get("modules", [])  # validated when plan.json was written
    held = refused(subject, [str(m["id"]) for m in modules])
    marked = [m | {"teachable": m["id"] not in held} for m in modules]
    return plan | {"modules": marked}
