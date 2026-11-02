# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``plan_today`` ticks steps off by itself when the server saw the work done."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

from tutor import credit
from tutor.relay import plan_auto, protocol
from tutor.relay.chat import CHAT_HANDLERS
from tutor.store import data_dir
from tutor.tests._cur import D, H, card, make_ctx, module, review, subject, taught

if TYPE_CHECKING:
    import pytest

    from tutor.curriculum.context import Context
    from tutor.relay.context import RequestContext

DEV = "00000000-0000-4000-8000-000000000000"
NOW = 1_800_000_000.0
NOW_MS = int(NOW * 1000)
DAY = credit.local_day(NOW)[0]
YESTERDAY = NOW_MS - D


def _call(
    kind: str, body: dict[str, Any] | None = None, cur: Context | None = None
) -> dict[str, Any]:
    req = {"kind": kind, "dev": DEV, "created": 1, "body": body or {}}
    ctx = SimpleNamespace(
        now=lambda: NOW,
        body=protocol.validate("0" * 26, req).body,
        request=None,
        engine=SimpleNamespace(ctx=cur),
    )
    return asyncio.run(CHAT_HANDLERS[kind](cast("RequestContext", ctx)))


def _plan(*steps: tuple[str, str, str]) -> None:
    rows = [
        {"id": i, "title": i, "what": "w", "kind": k, "target": t} for i, k, t in steps
    ]
    path = data_dir() / "plan" / f"{DAY}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"steps": rows}), encoding="utf-8")


def _put(folder: str, name: str, body: object) -> None:
    path = data_dir() / folder / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body), encoding="utf-8")


def _done() -> dict[str, bool]:
    return {s["id"]: s["done"] for s in _call("plan_today")["steps"]}


def test_a_coach_session_that_reached_exit_today_ticks_its_slug() -> None:
    _plan(("a", "coach", "two-sum"), ("b", "coach", "old"), ("c", "coach", "open"))
    _put("lc_sessions", "aaaaaaaaaaaa", {"slug": "two-sum", "exit_ms": NOW_MS - 5})
    _put("lc_sessions", "bbbbbbbbbbbb", {"slug": "old", "exit_ms": YESTERDAY})
    _put("lc_sessions", "cccccccccccc", {"slug": "open", "phase": "work"})
    (data_dir() / "lc_sessions" / "dddddddddddd.json").write_text(
        "{x", encoding="utf-8"
    )
    (data_dir() / "lc_sessions" / "eeeeeeeeeeee.json").write_text(
        "[1]", encoding="utf-8"
    )
    assert _done() == {"a": True, "b": False, "c": False}
    assert _call("plan_today")["current"] == "b"


def test_a_tick_is_sticky_and_written_once() -> None:
    _plan(("a", "coach", "two-sum"), ("b", "note", ""))
    _put("lc_sessions", "aaaaaaaaaaaa", {"slug": "two-sum", "exit_ms": NOW_MS})
    assert _done()["a"] is True
    (data_dir() / "lc_sessions" / "aaaaaaaaaaaa.json").unlink()
    assert _done() == {"a": True, "b": False}
    raw = json.loads((data_dir() / "plan" / f"{DAY}.json").read_text(encoding="utf-8"))
    assert raw["done"] == ["a"]


def test_an_explicit_done_still_works_beside_the_ticks() -> None:
    _plan(("a", "coach", "two-sum"), ("b", "note", ""), ("c", "coach", "x"))
    _put("lc_sessions", "aaaaaaaaaaaa", {"slug": "two-sum", "exit_ms": NOW_MS})
    after = _call("plan_step_done", {"id": "b"})
    assert [s["done"] for s in after["steps"]] == [True, True, False]
    assert after["current"] == "c"
    again = _call("plan_step_done", {"id": "a"})
    assert again["current"] == "c"
    raw = json.loads((data_dir() / "plan" / f"{DAY}.json").read_text(encoding="utf-8"))
    assert sorted(raw["done"]) == ["a", "b"]


def test_a_write_failure_still_returns_the_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _plan(("a", "coach", "two-sum"))
    _put("lc_sessions", "aaaaaaaaaaaa", {"slug": "two-sum", "exit_ms": NOW_MS})

    def boom(self: Path, target: Path) -> Path:
        del self, target
        raise OSError

    monkeypatch.setattr(Path, "replace", boom)
    assert _done() == {"a": True}


def _mock(name: str, finished_ms: int | None) -> None:
    body: dict[str, Any] = {"id": name, "answers": {}}
    if finished_ms is not None:
        body["result"] = {"finished_ms": finished_ms, "score": 1}
    _put("mocks", name, body)


def test_a_mock_finished_today_ticks_the_mock_and_later_its_review() -> None:
    _plan(("m", "mock", "60"), ("r", "mock", "review"))
    _mock("aaaaaaaaaaaa", None)
    _mock("bbbbbbbbbbbb", YESTERDAY)
    assert _done() == {"m": False, "r": False}
    _mock("cccccccccccc", NOW_MS - 2 * 60_000)
    assert _done() == {"m": True, "r": False}
    _mock("dddddddddddd", NOW_MS - plan_auto.REVIEW_MS)
    assert _done() == {"m": True, "r": True}


def test_unreadable_mocks_are_skipped() -> None:
    _plan(("m", "mock", "60"))
    (data_dir() / "mocks").mkdir(parents=True)
    (data_dir() / "mocks" / "x.json").write_text("{x", encoding="utf-8")
    _put("mocks", "y", [1])
    _put("mocks", "z", {"result": {"score": 1}})
    assert _done() == {"m": False}


def test_a_lesson_that_mastered_a_concept_today_ticks_its_topic() -> None:
    _plan(("a", "sql_lesson", "dates"), ("b", "sql_lesson", "basics"))
    _put("sql_lessons", "aaaaaaaaaaaa", {"topic": "dates", "mastered_ms": NOW_MS - 9})
    _put("sql_lessons", "bbbbbbbbbbbb", {"topic": "basics", "mastered_ms": YESTERDAY})
    _put("sql_lessons", "cccccccccccc", {"topic": "basics", "turn": 3})
    (data_dir() / "sql_lessons" / "dddddddddddd.json").write_text(
        "{x", encoding="utf-8"
    )
    _put("sql_lessons", "eeeeeeeeeeee", [1])
    assert _done() == {"a": True, "b": False}


def _deck(tmp: Path) -> Context:
    cur, fakes = make_ctx(tmp)
    fakes.now[0] = NOW_MS
    subject(
        cur,
        "hosting",
        modules=[module("a", status="ready")],
        found={f"c{i}": card("a", i) for i in range(3)},
    )
    return cur


def test_cards_tick_when_nothing_is_due_and_some_were_studied_today(
    tmp_path: Path,
) -> None:
    cur = _deck(tmp_path / "cur")
    _plan(("c", "cards", "hosting"), ("u", "cards", "nope"), ("v", "cards", "../x"))
    assert _call("plan_today", cur=cur)["current"] == "c"  # untouched: not done
    taught(cur, "hosting", "c0", NOW_MS - 10 * D, 0)
    assert _call("plan_today", cur=cur)["current"] == "c"  # due since long ago
    review(cur, "hosting", "c0", NOW_MS - H, 3)
    got = _call("plan_today", cur=cur)
    assert {s["id"]: s["done"] for s in got["steps"]} == {
        "c": True,
        "u": False,
        "v": False,
    }


def test_a_new_card_taught_today_counts_as_studied(tmp_path: Path) -> None:
    cur = _deck(tmp_path / "cur")
    _plan(("c", "cards", "hosting"))
    taught(cur, "hosting", "c1", NOW_MS - H, 1)
    assert _call("plan_today", cur=cur)["current"] is None


def test_a_review_only_yesterday_is_not_studied_today(tmp_path: Path) -> None:
    cur = _deck(tmp_path / "cur")
    _plan(("c", "cards", "hosting"))
    taught(cur, "hosting", "c2", YESTERDAY - H, 2)
    assert _call("plan_today", cur=cur)["current"] == "c"


def test_drill_and_note_steps_are_never_ticked() -> None:
    _plan(("d", "sql_drill", "dates"), ("n", "note", ""))
    assert _done() == {"d": False, "n": False}
