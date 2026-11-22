# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""A PC drill minute's row names its card's module, like an app review's (C1)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import earned_time

from tutor import drill, review_credit
from tutor.ledger_io import default_paths
from tutor.ledger_twin import is_tagged
from tutor.store import Store
from tutor.tests._credit_support import put
from tutor.tests._cur import T0, card, make_ctx, module, subject, taught
from tutor.tests._review_support import ledger_entries
from tutor.tests.conftest import KEY

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.curriculum.context import Context

NOW = T0 / 1000 + 30 * 86_400
TAGS = {"subject", "module", "activity"}


def _minute(tmp_path: Path) -> tuple[Context, dict[str, Any]]:
    """One drill answer on card a1 of module ``a`` that pays its first minute."""
    ctx, _ = make_ctx(tmp_path)
    subject(ctx, modules=[module("a", status="ready")], found={"a1": card("a", 1)})
    taught(ctx, "car", "a1", T0, 1)
    run = drill.Drill(Store(tmp_path), ctx)
    pid = run.next("car", NOW)["prompt_id"]
    assert run.answer(pid, 0, NOW + 70)["minute_credited"]
    (row,) = ledger_entries()
    return ctx, row


def test_a_drill_minute_row_names_the_answered_card_module(tmp_path: Path) -> None:
    _, row = _minute(tmp_path)
    assert row["entry_id"].startswith("drill-")
    detail = row["detail"]
    assert (detail["subject"], detail["module"], detail["activity"]) == (
        "car",
        "a",
        "review",
    )
    assert earned_time.verified(row, KEY)


def test_an_untagged_drill_row_of_today_gets_a_tagged_twin(tmp_path: Path) -> None:
    ctx, row = _minute(tmp_path)
    old = {k: v for k, v in row["detail"].items() if k not in TAGS}
    body = {k: v for k, v in row.items() if k != "hmac"} | {"detail": old}
    bare = body | {"hmac": earned_time.entry_signature(body, KEY)}
    put(default_paths(), [bare])
    review_credit.credit_now(ctx, NOW + 80)
    first, twin = ledger_entries()
    assert first == bare
    assert is_tagged(twin)
    assert twin["detail"]["module"] == "a"
    assert twin["entry_id"] == bare["entry_id"]
    review_credit.credit_now(ctx, NOW + 90)
    assert len(ledger_entries()) == 2
