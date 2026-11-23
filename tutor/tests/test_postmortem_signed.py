# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Signed post-mortem files fail closed; the worker loop; the small helpers."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

import pytest

from tutor import sources
from tutor.curriculum.context import Context
from tutor.postmortem import apply, files, proposal, report, show, signed, todo, watch
from tutor.relay import postmortem_task
from tutor.relay.curriculum_sync import CurriculumSync
from tutor.relay.postmortem_task import PostmortemWork
from tutor.store import data_dir
from tutor.tests import _pm
from tutor.tests._fake_rtdb import FakeRtdb
from tutor.tests._relay_support import engine, wiring

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_rows_fail_closed_without_a_key_or_on_a_broken_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "rows.json"
    assert signed.verified_rows(path, "k") == []
    assert signed.append_row(path, {"kind": "k", "n": 1}) is not None
    path.write_text(
        json.dumps(
            {
                "entries": [
                    *json.loads(path.read_text())["entries"],
                    {"kind": "k", "hmac": "é"},
                    3,
                ]
            }
        )
    )
    rows = signed.verified_rows(path, "k")
    assert rows is not None
    assert [r["n"] for r in rows] == [1]
    path.write_text("{")
    assert signed.verified_rows(path, "k") is None
    assert signed.append_row(path, {"kind": "k"}) is None
    monkeypatch.setenv("TUTOR_KEY", str(tmp_path / "missing.key"))
    assert signed.verified_rows(path, "k") is None
    assert signed.append_row(tmp_path / "x.json", {"kind": "k"}) is None
    assert not signed.write_doc(tmp_path / "d.json", {})
    assert signed.read_doc(tmp_path / "d.json") is None


def test_a_document_is_read_only_when_its_signature_holds(tmp_path: Path) -> None:
    path = tmp_path / "doc.json"
    assert signed.read_doc(path) is None
    assert signed.write_doc(path, {"kind": "x", "v": 1})
    assert signed.read_doc(path) == {
        "kind": "x",
        "v": 1,
        "hmac": json.loads(path.read_text())["hmac"],
    }
    path.write_text("[")
    assert signed.read_doc(path) is None
    assert not signed.valid(3, b"k")


def test_earlier_units_rates_and_history_of_revisions(
    caplog: pytest.LogCaptureFixture,
) -> None:
    entry = {"rev": 1, "one_shot": {"post": [1, 4]}, "seen": ["p1"]}
    for own in ("dry/prefix-sums.json", "failed/x-1.json", "tasks/t.filed.json"):
        (files.root() / own).parent.mkdir(parents=True, exist_ok=True)
        (files.root() / own).write_text('{"unsigned": true}', encoding="utf-8")
    assert report.save(_pm.LC, "other", entry)
    assert report.save(_pm.LC, _pm.UNIT, {**entry, "seen": ["p2"]})
    assert report.save(_pm.LC, "empty", {})
    path = files.report_path(_pm.LC, "empty")
    doc = json.loads(path.read_text())
    assert signed.write_doc(
        path, {**{k: v for k, v in doc.items() if k != "hmac"}, "revisions": []}
    )
    assert report.earlier(_pm.UNIT) == [{"unit": "other", "rev": 1, "post": [1, 4]}]
    assert "fails its signature" not in caplog.text  # dry/, failed/, tasks/ skipped
    assert report.seen(_pm.LC, _pm.UNIT) == {"p2"}
    assert proposal._rate([0, 0]) == "n/a"
    assert proposal._rate([1, 4]) == "1/4 (25%)"


def test_apply_records_an_edit_of_a_card_that_vanished(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(sources, "CACHE_DIR", tmp_path / "src-cache")
    ctx = Context(data_dir())
    _pm.unit_subject(ctx, teach=False)
    found = {
        "unit": _pm.UNIT,
        "subject": _pm.LC,
        "modules": ["a"],
        "new_cards": [],
        "cards": [
            {
                "id": "zz",
                "change": "edit",
                "front": "Q",
                "new_front": "N?",
                "new_back": "N.",
                "finding": "",
            },
            {
                "id": "a1",
                "change": "edit",
                "front": "Q",
                "new_front": "",
                "new_back": "Only the back.",
                "finding": "",
            },
        ],
    }
    out = apply.apply(ctx, found, 1)
    assert out["refused"] == [{"op": "edit", "card": "zz", "reason": "no such card"}]
    assert (out["edited"], out["untaught"]) == (
        ["a1"],
        [],
    )  # never taught: nothing to undo
    assert ctx.subjects.cards(_pm.LC)["a1"].front == "What is thing 1 of a?"


def test_show_and_todo_message_edges() -> None:
    card = {
        "change": "kept",
        "id": "a",
        "front": "F",
        "new_front": "",
        "new_back": "",
        "used_by": ["p"],
        "finding": "",
    }
    assert show._card(card) == ["  [kept] a: F", "    used by one-shot: p"]
    assert todo._message("data: [1]\n") == {}
    assert todo._message("") == {}
    assert todo._message("data: {broken\n") == {}


def test_a_failed_marker_skips_only_its_unit(tmp_path: Path) -> None:
    for slug in ("p1", "p2", "p3"):
        _pm.history(slug, ("Accepted", 1, "c"))
    _pm.write_rows("finish", _pm.guard_row(unit="first"), _pm.guard_row())
    marker = files.failed_path("first", 1)
    marker.parent.mkdir(parents=True)
    marker.write_text("{}")
    found = watch.due(_pm.AT)
    assert found is not None
    assert found[0].unit == _pm.UNIT
    del tmp_path


def test_the_worker_loop_ticks_syncs_and_survives(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    eng, _ = engine(tmp_path)
    w = wiring(FakeRtdb(), eng)
    sync = CurriculumSync(w)
    synced: list[int] = []

    async def fake_sync() -> None:
        synced.append(1)

    monkeypatch.setattr(sync, "sync", fake_sync)
    busy = [True]
    work = PostmortemWork(w, sync, lambda: busy[0])
    outcomes = ["done", "idle"]
    monkeypatch.setattr(watch, "tick", lambda ctx, now: outcomes.pop(0))
    assert asyncio.run(work.once()) == "busy"
    busy[0] = False
    assert asyncio.run(work.once()) == "done"
    assert asyncio.run(work.once()) == "idle"
    assert synced == [1]
    rounds: list[int] = []

    async def once() -> str:
        rounds.append(1)
        if len(rounds) == 1:
            msg = "boom"
            raise ValueError(msg)
        work.stopped = True
        return "idle"

    async def no_sleep(_s: float) -> None:
        return None

    monkeypatch.setattr(work, "once", once)
    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    asyncio.run(work.run())
    assert len(rounds) == 2
    monkeypatch.setenv(postmortem_task.SWITCH_ENV, "off")
    asyncio.run(work.run())
    assert len(rounds) == 2
