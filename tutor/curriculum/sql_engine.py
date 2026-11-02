# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Run a card's example query on a throwaway MySQL database (``sql_drills``).

The one place the SQL cards touch Docker. ``sql_drills`` is a sibling package
(``~/src/utils/sql_drills``) that exposes drills, not ad-hoc schemas, so the
sandbox it builds drills on is used directly.
"""

from __future__ import annotations

import importlib
from typing import Final

from tutor.curriculum.sql_card_spec import Outcome

_NO_TABLES: Final = "SELECT 1;"  # an empty schema is not valid SQL for the engine


def run_query(schema: str, query: str) -> Outcome:
    """``query`` on a fresh database built from ``schema``; the container is started.

    A MySQL error is an ``Outcome`` with its code (a card may teach an error);
    only an engine failure (Docker, sandbox) raises.
    """
    sd = importlib.import_module("sql_drills")
    sandbox = importlib.import_module("sql_drills._sandbox").sandbox
    sd.ensure_running()
    with sandbox(schema or _NO_TABLES) as box:
        done = box.execute(query)
    return Outcome(done.ok, tuple(tuple(row) for row in done.rows), done.code)
