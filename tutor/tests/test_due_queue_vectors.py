# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The due queue's rule against ``contract/due_queue_vectors.json``.

The app's ``reviewQueue`` runs the same file (``app/test/log/due_queue_test.dart``),
so the signed ``review_due.json`` and the route ``/review/<subject>/<module>``
mean the same card set: taught, not flagged at the current rev, not suspended,
``due <= now``. Two Python legs: the queue rule (``no_card``) and the writer of
the signed file (``review_due.due_times``, which reads the log and the store).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tutor.curriculum import review_due
from tutor.curriculum.eventlog import EventLog
from tutor.curriculum.fold import fold
from tutor.curriculum.no_card import due_in_subject, due_now
from tutor.curriculum.records import Plan
from tutor.curriculum.rules import View
from tutor.tests._cur import card, module
from tutor.tests._due import LC, make_lc

_VECTORS = Path(__file__).resolve().parents[2] / "contract" / "due_queue_vectors.json"
_CASES: list[dict[str, Any]] = json.loads(_VECTORS.read_text())


def _view(cards: dict[str, dict[str, Any]]) -> View:
    recs = {
        cid: card("a", i, rev=info["rev"], suspended=info["suspended"])
        for i, (cid, info) in enumerate(cards.items(), start=1)
    }
    return View("car", Plan(1, "approved", "", [module("a", status="ready")]), recs)


@pytest.mark.parametrize("case", _CASES, ids=[c["name"] for c in _CASES])
def test_python_rule_matches_the_shared_vectors(case: dict[str, Any]) -> None:
    folded = fold(case["events"])
    view = _view(case["cards"])
    for check in case["checks"]:
        want = sorted(check["due"])
        assert sorted(due_now(view, folded, check["now"])) == want
        assert due_in_subject(view, folded, check["now"]) == len(want)


@pytest.mark.parametrize("case", _CASES, ids=[c["name"] for c in _CASES])
def test_the_signed_file_counts_the_same_cards(
    case: dict[str, Any], tmp_path: Path
) -> None:
    """``due_times`` (what ``review_due.json`` lists) agrees with the vectors."""
    recs = {
        cid: card("a", i, rev=info["rev"], suspended=info["suspended"])
        for i, (cid, info) in enumerate(case["cards"].items(), start=1)
    }
    make_lc(tmp_path, **recs)
    EventLog(tmp_path).append({**e, "s": LC} for e in case["events"])
    listed = review_due.due_times(tmp_path, LC)["a"]
    for check in case["checks"]:
        assert sum(due <= check["now"] for due in listed) == len(check["due"])
