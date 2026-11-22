# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""C3: which modules of the gated LeetCode subjects the tutor may teach now.

leetcode-guard writes one signed row to ``theory_phase.json``
(``DOCS-contract-theory-phase.md``); ``detail.teachable`` lists the
``(subject, module)`` pairs of the current unit while the guard is in
THEORY. A module of a :data:`GATED` subject not in that list is never
taught and never marked taught. Fail closed: a missing, unreadable, unsigned,
foreign or malformed file means nothing is teachable, logged as ONE warning
per read and never raised. Ungated subjects never read the file.

The path resolves at call time: ``TUTOR_THEORY_PHASE`` moves it (the tests
point it into ``tmp_path``), else it is the guard's data dir under ``HOME``.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Final

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

type Pairs = frozenset[tuple[str, str]]


def phase_path() -> Path:
    """Where the guard writes the row (``TUTOR_THEORY_PHASE`` overrides)."""
    found = os.environ.get("TUTOR_THEORY_PHASE")
    if found:
        return Path(found)
    return Path.home() / ".local/share/leetcode_guard/theory_phase.json"


def _pairs(row: object, key: bytes) -> Pairs | None:
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
    return pairs if detail["phase"] == "theory" or not pairs else None


def teachable() -> Pairs:
    """The guard's signed ``teachable`` pairs; empty on any failure (one warning)."""
    path = phase_path()
    try:
        row = json.loads(path.read_text(encoding="utf-8"))
        key = default_paths().key_file.read_bytes().strip()
        # TypeError: compare_digest refuses a non-ASCII ``hmac`` string.
        found = _pairs(row, key)
    except (OSError, ValueError, TypeError) as exc:
        _logger.warning("theory phase %s unreadable, nothing teachable: %s", path, exc)
        return frozenset()
    if found is None:
        _logger.warning("theory phase %s not a signed C3 row, nothing teachable", path)
        return frozenset()
    return found


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
