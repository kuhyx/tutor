# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The post-mortem's measurements: one-shot, tries, minutes, pre/post theory."""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING

import pytest

from tutor import sources
from tutor.curriculum.context import Context
from tutor.postmortem import evidence, files
from tutor.rework_context import guard_dir
from tutor.store import data_dir
from tutor.tests import _pm

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def cur(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Context:
    monkeypatch.setattr(sources, "CACHE_DIR", tmp_path / "src-cache")
    return Context(data_dir())


def test_a_clean_first_accepted_with_no_coach_help_is_one_shot() -> None:
    _pm.history("p1", ("Accepted", 100, "code1"), ("Wrong Answer", 200, "later"))
    got = evidence.solve_of("p1", done_at=50)
    assert (got.tries, got.ac_at, got.code, got.post, got.one_shot) == (
        0,
        100,
        "code1",
        True,
        True,
    )
    assert got.row()["phase"] == "post"
    assert got.statuses == ["Accepted"]


def test_misses_before_accepted_and_coach_help_break_the_one_shot() -> None:
    _pm.history(
        "p2",
        ("Wrong Answer", 300, "bad" * 600),
        ("Accepted", 400, "good"),
        ("Runtime Error", 10, ""),
    )
    got = evidence.solve_of("p2", done_at=500)
    assert (got.tries, got.post, got.one_shot) == (2, False, False)
    assert got.failed_code.endswith("[...]")
    assert got.statuses == ["Runtime Error", "Wrong Answer", "Accepted"]
    sessions = data_dir() / "lc_sessions"
    sessions.mkdir(parents=True)
    (sessions / "x.json").write_text(json.dumps({"slug": "p3", "rungs": [1, 2]}))
    (sessions / "y.json").write_text(json.dumps({"slug": "p3", "revealed": True}))
    _pm.history("p3", ("Accepted", 100, "c"))
    hinted = evidence.solve_of("p3", done_at=None)
    assert (hinted.hints, hinted.revealed, hinted.one_shot, hinted.post) == (
        2,
        True,
        False,
        False,
    )


def test_an_unsolved_or_missing_history_is_no_accepted() -> None:
    _pm.history("p4", ("Wrong Answer", 1, "x"))
    got = evidence.solve_of("p4", done_at=0)
    assert (got.ac_at, got.tries, got.one_shot, got.code) == (None, 1, False, "")
    gone = evidence.solve_of("nothing", done_at=0)
    assert (gone.ac_at, gone.tries, gone.minutes) == (None, 0, None)
    assert not evidence.has_code("nothing")
    _pm.history("p5", ("Accepted", 1, ""))
    assert not evidence.has_code("p5")
    _pm.history("p6", ("Accepted", 1, "code"))
    assert evidence.has_code("p6")


def test_minutes_count_gaps_up_to_five_minutes_until_the_accepted() -> None:
    assert evidence.minutes([], 10) is None
    assert evidence.minutes([0, 60, 120], 180) == 3
    assert evidence.minutes([0, 60, 1000], None) == 1  # the 940 s gap is idle
    assert evidence.minutes([0, 60], 30) == 1  # an end before the last beat is ignored
    _pm.attempts("p1", [100, 160, 220, 9999])
    _pm.history("p1", ("Accepted", 280, "c"))
    assert evidence.solve_of("p1", done_at=None).minutes == 3
    (guard_dir() / "attempts.json").write_text("{broken")
    assert evidence.solve_of("p1", done_at=None).minutes is None


def test_requests_refuse_malformed_rows() -> None:
    good = _pm.guard_row()
    assert evidence.parse_request(good) == evidence.Request(
        "prefix-sums", _pm.LC, ("a",), _pm.AT, ("p1", "p2", "p3")
    )
    bad_details: list[object] = [
        None,
        {**good["detail"], "unit": ""},
        {**good["detail"], "at": True},
        {**good["detail"], "at": "x"},
        {**good["detail"], "modules": "a"},
        {**good["detail"], "solves": ["../x"]},
    ]
    for detail in bad_details:
        assert evidence.parse_request({**good, "detail": detail}) is None


def test_theory_done_at_is_the_latest_modules_first_done(cur: Context) -> None:
    root = cur.data_dir
    assert evidence.theory_done_at(root, _pm.LC, ("a",)) is None
    before = time.time()
    _pm.unit_subject(cur)
    done = evidence.theory_done_at(root, _pm.LC, ("a",))
    assert done is not None
    assert done >= before
    assert evidence.theory_done_at(root, _pm.LC, ("a", "b")) is None
    assert evidence.theory_done_at(root, _pm.LC, ()) is None
    assert evidence.theory_done_at(root, "other", ("a",)) is None


def test_files_refuse_a_name_that_is_not_a_slug() -> None:
    with pytest.raises(ValueError, match="not a slug"):
        files.report_path(_pm.LC, "../x")
