# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The worker tick: a finished unit's post-mortem runs once, applies, records."""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Any, ClassVar, Self
import urllib.request

import pytest

from tutor import sources
from tutor.curriculum import card_ops
from tutor.curriculum.context import Context
from tutor.curriculum.errors import CLAUDE_UNAVAILABLE, RequestError
from tutor.postmortem import apply, cli, files, lessons, report, signed, todo, watch
from tutor.store import data_dir
from tutor.tests import _pm

if TYPE_CHECKING:
    from pathlib import Path


class FakeTodo:
    """The todo MCP endpoint: records each ``add_task``."""

    def __init__(self, *, down: bool = False) -> None:
        self.tasks: list[dict[str, str]] = []
        self.down = down

    def __call__(
        self, url: str, headers: dict[str, str], payload: dict[str, Any]
    ) -> tuple[dict[str, str], str]:
        if self.down:
            msg = "down"
            raise todo.TodoError(msg)
        if payload.get("method") == "initialize":
            return {"Mcp-Session-Id": "s1"}, "{}"
        if payload.get("method") == "tools/call":
            assert headers["Mcp-Session-Id"] == "s1"
            self.tasks.append(payload["params"]["arguments"])
            reply = {"result": {"content": [{"type": "text", "text": "id1"}]}}
            return {}, "data: " + json.dumps(reply)
        return {}, ""


@pytest.fixture
def mcp(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FakeTodo:
    fake = FakeTodo()
    token = tmp_path / "todo_token"
    token.write_text("t0k\n")
    monkeypatch.setenv(todo.TOKEN_FILE_ENV, str(token))
    monkeypatch.setattr(todo, "http_post", fake)
    monkeypatch.setattr(todo.flush, "__defaults__", (fake,))
    return fake


@pytest.fixture
def cur(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Context:
    monkeypatch.setattr(sources, "CACHE_DIR", tmp_path / "src-cache")
    ctx = Context(data_dir())
    _pm.unit_subject(ctx)
    late = int(time.time()) + 3600
    _pm.history("p1", ("Accepted", late, "prefix"))
    _pm.history("p2", ("Wrong Answer", late, "x"), ("Accepted", late + 1, "y"))
    _pm.history("p3", ("Accepted", late + 2, "z"))
    _pm.write_rows("finish", _pm.guard_row())
    return ctx


def _flips(root: Path) -> list[bool]:
    raw = json.loads((root / "module_state.json").read_text())
    return [r["detail"]["done"] for r in raw["entries"]]


def test_a_finished_unit_is_analysed_once_and_its_cards_fixed(
    cur: Context, mcp: FakeTodo
) -> None:
    cur.draft = lambda *_: _pm.reply()
    before = dict(cur.subjects.cards(_pm.LC))
    assert _flips(cur.data_dir) == [True]
    assert watch.tick(cur, time.time()) == "done"
    cards = cur.subjects.cards(_pm.LC)
    taught = cur.fold().taught_ids(_pm.LC)
    assert cards["a0"] == before["a0"]  # kept: used by the one-shot p1
    assert "a0" in taught
    assert (cards["a1"].front, cards["a1"].rev) == ("Better a1?", 2)
    assert cards["a1"].source.startswith(apply.SOURCE_HOST)
    assert "a1" not in taught  # edited: to be passed again
    assert cards["a2"].suspended
    new = [
        c for c in cards.values() if c.tutor.get("source") == "postmortem:prefix-sums:1"
    ]
    assert [c.front for c in new] == ["When does a prefix sum need a 0 sentinel?"]
    assert _flips(cur.data_dir) == [True, False]  # the re-pass is owed at once
    entry = report.revisions(_pm.LC, _pm.UNIT)[0]
    assert entry["rev"] == 1
    assert entry["applied"]["untaught"] == ["a1"]
    assert entry["applied"]["suspended"] == [{"id": "a2", "reason": "misleading"}]
    assert entry["seen"] == ["p1", "p2", "p3"]
    rows = signed.verified_rows(files.revisions_path(), files.REV_KIND)
    assert rows is not None
    assert [r["detail"]["rev"] for r in rows] == [1]
    # The guard pays the re-pass only for a done: false signed AFTER the
    # revision's at (F32, 2026-11-23): the apply's own row must count.
    undone = json.loads((cur.data_dir / "module_state.json").read_text())
    assert rows[0]["detail"]["at"] < undone["entries"][-1]["detail"]["at"]
    assert "Teach the sentinel" in lessons.text(_pm.LC)
    assert [t["title"] for t in mcp.tasks] == [
        "Apply post-mortem prefix-sums: future modules + skills"
    ]
    assert "- Q: B? A: B. (sentinel)" in mcp.tasks[0]["body"]
    assert mcp.tasks[0]["repo"] == "kuhyx/tutor"
    assert watch.tick(cur, time.time()) == "idle"  # nothing unseen: no second run
    _pm.write_rows(
        "finish", _pm.guard_row(), _pm.guard_row(solves=["p1", "p2", "p3", "p4"], n=2)
    )
    assert watch.tick(cur, time.time()) == "idle"  # one new solve is not enough


def test_a_failure_writes_nothing_files_one_task_and_stops(
    cur: Context, mcp: FakeTodo, caplog: pytest.LogCaptureFixture
) -> None:
    calls: list[str] = []

    def down(*_: Any) -> Any:
        calls.append("x")
        msg = "network down"
        raise RequestError(CLAUDE_UNAVAILABLE, msg)

    cur.draft = down
    before = dict(cur.subjects.cards(_pm.LC))
    with caplog.at_level(logging.WARNING, logger=watch.__name__):
        assert watch.tick(cur, time.time()) == "failed"
    assert len(caplog.records) == 1  # C5: one warning per failure (F32)
    assert cur.subjects.cards(_pm.LC) == before
    assert report.revisions(_pm.LC, _pm.UNIT) == []
    assert [t["title"] for t in mcp.tasks] == ["Post-mortem prefix-sums failed"]
    assert "postmortem prefix-sums --retry" in mcp.tasks[0]["body"]
    assert watch.tick(cur, time.time()) == "idle"
    assert (len(calls), len(mcp.tasks)) == (1, 1)
    assert cli.main([_pm.UNIT, "--retry"]) == 0
    cur.draft = lambda *_: _pm.reply()
    assert watch.tick(cur, time.time()) == "done"


def test_the_tick_waits_for_code_and_threshold(cur: Context, mcp: FakeTodo) -> None:
    _pm.history("p3", ("Accepted", 1, ""))
    assert watch.due(_pm.AT + 60) is None  # p3's code is not mirrored yet
    found = watch.due(_pm.AT + 25 * 3600)  # a day later it runs without it
    assert found is not None
    assert found[1] == 1
    _pm.write_rows("finish", _pm.guard_row(solves=["p1", "p2"]))
    assert watch.due(_pm.AT + 25 * 3600) is None
    forged = _pm.guard_row()
    forged["detail"]["solves"] = ["p1", "p2", "p3", "p4"]
    _pm.write_rows("finish", forged, _pm.guard_row(unit="x") | {"hmac": "00"})
    assert watch.requests() == []
    _pm.write_rows("finish", _pm.guard_row(solves=["../x"]))
    assert watch.requests() == []  # signed but malformed
    del mcp


def test_refusals_are_recorded_and_the_rest_applied(
    cur: Context, mcp: FakeTodo, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(*_: Any, **__: Any) -> Any:
        code, msg = "edit_refused", "no"
        raise RequestError(code, msg)

    monkeypatch.setattr(card_ops, "add", refuse)
    monkeypatch.setattr(card_ops, "remove", refuse)
    reply = _pm.reply()
    reply["cards"].append(
        {"id": "gone", "verdict": "edit", "front": "Q?", "back": "A.", "finding": ""}
    )
    cur.draft = lambda *_: reply
    assert watch.tick(cur, time.time()) == "done"
    applied = report.revisions(_pm.LC, _pm.UNIT)[0]["applied"]
    assert [r["op"] for r in applied["refused"]] == ["add", "suspend"]
    assert applied["edited"] == ["a1"]
    del mcp


def test_todo_tasks_queue_once_and_wait_out_an_outage(
    cur: Context, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    assert todo.queue("t1", "T", "B")
    assert not todo.queue("t1", "T", "B")
    down = FakeTodo(down=True)
    assert todo.flush(down) == 0  # no token yet
    token = tmp_path / "tok"
    token.write_text("")
    monkeypatch.setenv(todo.TOKEN_FILE_ENV, str(token))
    assert todo.flush(down) == 0  # an empty token
    token.write_text("x")
    assert todo.flush(down) == 0
    assert todo.pending()
    up = FakeTodo()
    assert todo.flush(up) == 1
    assert todo.pending() == []
    assert not todo.queue("t1", "T", "B")  # filed once, never again

    def refused(url: str, headers: dict[str, str], payload: dict[str, Any]) -> Any:
        if payload.get("method") == "tools/call":
            return {}, json.dumps({"result": {"isError": True}})
        return {}, "not json"

    todo.queue("t2", "T", "B")
    assert todo.flush(refused) == 0
    del cur


def test_http_post_returns_headers_and_body(monkeypatch: pytest.MonkeyPatch) -> None:
    class Reply:
        headers: ClassVar = {"Mcp-Session-Id": "s"}

        def __enter__(self) -> Self:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def read(self) -> bytes:
            return b"ok"

    seen: list[Any] = []

    def opened(req: Any, timeout: float) -> Reply:
        del timeout
        seen.append(req)
        return Reply()

    monkeypatch.setattr(urllib.request, "urlopen", opened)
    assert todo.http_post("http://x/mcp", {"A": "b"}, {"k": 1}) == (
        {"Mcp-Session-Id": "s"},
        "ok",
    )
    assert seen[0].data == b'{"k": 1}'

    def boom(*_: Any, **__: Any) -> Any:
        msg = "refused"
        raise OSError(msg)

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    with pytest.raises(todo.TodoError, match="cannot reach"):
        todo.http_post("http://x/mcp", {}, {})
