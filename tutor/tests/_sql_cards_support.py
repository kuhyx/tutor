# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Shared wiring for the SQL card tests: a fake engine and a MySQL subject."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tutor.curriculum import sql_cards
from tutor.curriculum.sql_bank import BANK
from tutor.curriculum.sql_card_spec import Outcome
from tutor.tests._cur import make_ctx, module, subject

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.curriculum.context import Context
    from tutor.tests._cur import Fakes

SUBJ = sql_cards.SUBJECT
NULLS = BANK["NULL comparisons"]


def runner(schema: str, query: str) -> Outcome:
    """A fake engine: NULL, NULL for the ``x =`` query, else one row ``1``."""
    del schema
    if "x =" in query:
        return Outcome(ok=True, rows=(("NULL",), ("NULL",)))
    return Outcome(ok=True, rows=(("1",),))


def sql_subject(tmp_path: Path) -> tuple[Context, Fakes]:
    """An approved MySQL subject with one ready module and no cards."""
    ctx, fakes = make_ctx(tmp_path)
    mods = [module("select-group-basics", status="ready", cards=0)]
    subject(ctx, SUBJ, modules=mods, found={})
    return ctx, fakes
