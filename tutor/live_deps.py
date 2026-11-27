# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The pinned dependencies a venv still lacks: ``python -m tutor.live_deps``.

``tutor.service`` runs on ``~/src/tutor/.venv``, which no deploy touched, so
a pin bumped in ``pyproject.toml`` (an httpx, a kuhyx/utils tag) never reached
the live server. ``scripts/tutor_deploy.sh`` runs this with the unit's own
python and ``pip install``s what it prints. An exact pin (``name==ver``) is
current when that version is installed; a git pin (``name @ git+URL@REV``)
when the installed copy's ``direct_url.json`` names the same revision.
Anything else cannot be checked, so it is printed (pip skips what is met).
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import logging
from pathlib import Path
import re
import sys
import tomllib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

_logger = logging.getLogger(__name__)
_EXACT = re.compile(r"^([A-Za-z0-9._-]+)==([^\s;]+)$")
_GIT = re.compile(r"^([A-Za-z0-9._-]+)\s*@\s*git\+[^@\s]+@([^#\s]+)")


# name -> (installed version, git revision it came from), None when absent.
type Lookup = Callable[[str], tuple[str, str | None] | None]


def installed(name: str) -> tuple[str, str | None] | None:
    """``name``'s version and requested git revision in this interpreter."""
    try:
        dist = importlib.metadata.distribution(name)
    except importlib.metadata.PackageNotFoundError:
        _logger.warning("%s is not installed in this venv", name)
        return None
    raw = dist.read_text("direct_url.json")
    vcs = json.loads(raw).get("vcs_info", {}) if raw else {}
    return dist.version, vcs.get("requested_revision")


def _current(requirement: str, lookup: Lookup) -> bool:
    if found := _EXACT.match(requirement) or _GIT.match(requirement):
        have = lookup(found[1])
        index = 0 if found.re is _EXACT else 1
        return have is not None and have[index] == found[2]
    return False


def missing(requirements: Sequence[str], lookup: Lookup = installed) -> list[str]:
    """The requirements the venv does not hold at exactly that pin."""
    return [r for r in requirements if not _current(r.strip(), lookup)]


def main(argv: Sequence[str] | None = None) -> int:
    """Print one missing requirement per line (none: the venv is current)."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pyproject", type=Path)
    args = parser.parse_args(argv)
    project = tomllib.loads(args.pyproject.read_text(encoding="utf-8"))["project"]
    for requirement in missing(project.get("dependencies", [])):
        sys.stdout.write(requirement + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
