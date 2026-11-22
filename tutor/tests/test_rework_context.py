# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The rework chat's context: kuhy's history on one problem, read-only and bounded."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from tutor import rework_context as rc
from tutor.store import data_dir

if TYPE_CHECKING:
    import pytest

SLUG = "two-sum"


def _write(path: Path, raw: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(raw if isinstance(raw, str) else json.dumps(raw), "utf-8")


def _history(raw: object) -> None:
    _write(rc.guard_dir() / "history" / f"{SLUG}.json", raw)


def _attempts(raw: object) -> None:
    _write(rc.guard_dir() / "attempts.json", raw)


def _session(name: str, raw: object) -> None:
    _write(data_dir() / "lc_sessions" / f"{name}.json", raw)


def test_the_guard_dir_is_the_env_var_else_under_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    assert rc.guard_dir() == tmp_path / "guard"
    monkeypatch.delenv(rc.GUARD_ENV)
    assert rc.guard_dir() == Path.home() / ".local/share/leetcode_guard"


def test_nothing_on_file_is_said_plainly() -> None:
    got = rc.gather(SLUG)
    assert got.text == rc.NOTHING
    assert got.counts() == {"submissions": 0, "days": 0, "sessions": 0}


def test_broken_files_are_left_out_with_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    _history("{not json")
    _attempts(["not", "a", "dict"])
    _session("aaaaaaaaaaaa", "{bad")
    with caplog.at_level(logging.WARNING):
        got = rc.gather(SLUG)
    assert got.counts() == {"submissions": 0, "days": 0, "sessions": 0}
    assert "unreadable" in caplog.text
    _history({"submissions": "nope"})
    _attempts({"records": "nope"})
    assert rc.gather(SLUG).counts()["submissions"] == 0


def test_submissions_newest_first_with_capped_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rc, "MAX_CODE", 4)
    _history(
        {
            "submissions": [
                "junk",
                {"status": "Wrong Answer", "timestamp": "soon", "lang": "python3"},
                {
                    "status": "Accepted",
                    "timestamp": 1_795_287_000,
                    "lang": "python3",
                    "runtime": "40 ms",
                    "memory": "17 MB",
                    "code": "print(1)",
                },
            ]
        }
    )
    got = rc.gather(SLUG)
    assert got.counts()["submissions"] == 2
    first, second = got.text.split("\n- ")[1:3]
    assert first.startswith("2026-11-21 Accepted python3 40 ms 17 MB")
    assert "prin [...]" in first
    assert second.startswith("? Wrong Answer python3")


def test_attempt_days_of_this_slug_only() -> None:
    record = {
        "day": "2026-11-21",
        "slug": SLUG,
        "beats": [[1, "description"], [2, "editorial"], [3, "description"], "x"],
        "submissions": {"9": {"status": "Wrong Answer", "at": 3}, "8": "x"},
        "theory_at_solve": "done",
    }
    other = {**record, "slug": "valid-anagram"}
    _attempts({"records": {"a": record, "b": other, "c": "junk"}})
    got = rc.gather(SLUG)
    assert got.counts()["days"] == 1
    assert (
        "- 2026-11-21: 3 beats (description, editorial); "
        "submissions: Wrong Answer; theory at solve: done"
    ) in got.text
    _attempts({"records": {"a": {"slug": SLUG}}})
    assert "- ?: 0 beats (none); submissions: none; theory at solve: ?" in (
        rc.gather(SLUG).text
    )


def test_coach_sessions_newest_first_with_the_statement_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rc, "MAX_SESSIONS", 2)
    base = {
        "slug": SLUG,
        "title": "Two Sum",
        "phase": "done",
        "statement_md": "Given nums.",
        "belief": "sort first",
        "last_code": "def f(): pass",
        "thread": [{"mine": True, "md": "hi"}, {"mine": False, "md": "Which part?"}],
    }
    _session("aaaaaaaaaaaa", {**base, "updated_ms": 1, "phase": "gate"})
    _session("bbbbbbbbbbbb", {**base, "updated_ms": 3})
    _session("cccccccccccc", {**base, "updated_ms": 2, "thread": "junk"})
    _session("dddddddddddd", {**base, "slug": "other", "updated_ms": 9})
    _session("eeeeeeeeeeee", [1])
    got = rc.gather(SLUG)
    assert got.counts()["sessions"] == 2
    assert got.text.count("Given nums.") == 1
    assert "Coach session (done, Two Sum)" in got.text
    assert "phase gate" not in got.text
    assert "coach: Which part?" in got.text
    assert "Opening belief: sort first" in got.text


def test_no_sessions_dir_is_no_sessions() -> None:
    assert not (data_dir() / "lc_sessions").exists()
    assert rc.gather(SLUG).counts()["sessions"] == 0


def test_a_bare_coach_session_still_counts() -> None:
    _session("aaaaaaaaaaaa", {"slug": SLUG, "title": "Two Sum", "phase": "gate"})
    got = rc.gather(SLUG)
    assert got.text == "Coach session (gate, Two Sum)"
    assert got.counts()["sessions"] == 1
