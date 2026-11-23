# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Where the post-mortem reads and writes (``DOCS-contract-postmortem.md``).

Tutor side, under ``$TUTOR_DATA/postmortems/``:

- ``<subject>/<unit>.json``: the signed report, every revision (``report``).
- ``<subject>/lessons.json``: the signed lessons (``lessons``).
- ``revisions.json``: C7, one signed row per applied revision (the guard reads it).
- ``failed/<unit>-<rev>.json``: the failed marker; only ``--retry`` removes it.
- ``tasks/<name>.json``: todo tasks not filed yet (``todo``).
- ``dry/<unit>.json``: the last dry run's result (unsigned, display only).

Guard side (``rework_context.guard_dir``): ``unit_finish.json`` (C6) and
``postmortem_dry_run.json``, both written and signed by leetcode-guard.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from tutor.rework_context import SLUG, guard_dir
from tutor.store import data_dir

if TYPE_CHECKING:
    from pathlib import Path

FINISH_KIND: Final = "unit_finish"
PREVIEW_KIND: Final = "unit_preview"
REV_KIND: Final = "postmortem_rev"


def safe(name: str) -> str:
    """``name`` when it is a slug (it names a file), else ``ValueError``."""
    if not SLUG.fullmatch(name):
        msg = f"not a slug: {name!r}"
        raise ValueError(msg)
    return name


def root() -> Path:
    """``$TUTOR_DATA/postmortems``."""
    return data_dir() / "postmortems"


def report_path(subject: str, unit: str) -> Path:
    """The unit's signed report."""
    return root() / safe(subject) / f"{safe(unit)}.json"


def lessons_path(subject: str) -> Path:
    """The subject's signed lessons."""
    return root() / safe(subject) / "lessons.json"


def revisions_path() -> Path:
    """C7: the applied revisions, read by the guard."""
    return root() / "revisions.json"


def failed_path(unit: str, rev: int) -> Path:
    """The marker that stops every later tick for ``unit`` at ``rev``."""
    return root() / "failed" / f"{safe(unit)}-{rev}.json"


def tasks_dir() -> Path:
    """Todo tasks waiting to be filed."""
    return root() / "tasks"


def dry_path(unit: str) -> Path:
    """The last dry run's result for ``unit``."""
    return root() / "dry" / f"{safe(unit)}.json"


def finish_path() -> Path:
    """C6, the guard's signed finished-unit rows."""
    return guard_dir() / "unit_finish.json"


def preview_path() -> Path:
    """The guard's signed dry-run request (one row)."""
    return guard_dir() / "postmortem_dry_run.json"
