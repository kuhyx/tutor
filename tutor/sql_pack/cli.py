# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``python -m tutor sql-pack [--data DIR]``: save the hand-written drill pack."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
import sys
from typing import TYPE_CHECKING

from tutor.relay.sql import load_sd
from tutor.sql_pack import SPECS

_logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from types import ModuleType


def _save_all(sd: ModuleType) -> int:
    refused = 0
    for spec in SPECS:
        try:
            drill_id = sd.save_generated(spec)
        except sd.SpecError as exc:
            refused += 1
            _logger.warning("drill %r refused: %s", spec["title"], exc)
            sys.stdout.write(f"REFUSED {spec['title']}: {exc}\n")
            continue
        sys.stdout.write(f"{drill_id} {spec['topic']} {spec['kind']}\n")
    return refused


def main(argv: list[str]) -> int:
    """Print ``id topic kind`` per saved drill; 1 if the engine refused any."""
    parser = argparse.ArgumentParser(prog="python -m tutor sql-pack")
    parser.add_argument("--data", type=Path, default=None, help="drill store dir")
    args = parser.parse_args(argv)
    if args.data is not None:
        os.environ["SQL_DRILLS_DATA"] = str(args.data)
    sd = load_sd()
    sd.ensure_running()
    return 1 if _save_all(sd) else 0
