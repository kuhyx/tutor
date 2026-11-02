# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Failure paths of the mock handlers: model down, bad specs, odd stores."""

from __future__ import annotations

import asyncio
import json
import random
from typing import TYPE_CHECKING, Any

import pytest

from tutor.relay import mock_mcq, mock_sql, mock_store
from tutor.relay.errors import RequestError
from tutor.tests._mock_support import FakeSd, call, install, model, needs_bwrap

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def sd(monkeypatch: pytest.MonkeyPatch) -> FakeSd:
    return install(monkeypatch)


def test_answer_needs_a_task(sd: FakeSd) -> None:
    del sd
    mock_store.save({"id": "0" * 12, "tasks": [], "private": [], "answers": {}})
    with pytest.raises(RequestError):
        call({"op": "answer", "mock_id": "0" * 12})


@pytest.mark.parametrize(
    "spec",
    [
        {"title": "", "topic": "x", "task_md": "x", "schema_sql": "x"},
        {"title": "t", "topic": "x", "task_md": "x", "schema_sql": "x"},
    ],
)
def test_a_bad_spec_is_not_saved(
    monkeypatch: pytest.MonkeyPatch, sd: FakeSd, spec: dict[str, Any]
) -> None:
    monkeypatch.setattr(mock_sql, "ask_model", lambda *_: spec)
    assert asyncio.run(mock_sql._generate("dates")) is None
    assert sd.saved == []


def test_a_model_error_leaves_the_slot_to_a_saved_drill(
    monkeypatch: pytest.MonkeyPatch, sd: FakeSd
) -> None:
    del sd
    model(monkeypatch, [], spec=False)
    public, private, notes = asyncio.run(mock_sql.pick(random.SystemRandom(), set()))
    assert len(public) == len(private) == 3
    assert "No new SQL drill" in notes[0]


def test_unreadable_files_are_treated_as_empty(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "data/mock_bank.json").write_text("{not json", encoding="utf-8")
    assert mock_mcq._read_cache() == []
    (tmp_path / "data/mock_bank.json").write_text('{"a": 1}', encoding="utf-8")
    assert mock_mcq._read_cache() == []
    assert mock_mcq._verified(["junk", {"code": "x", "wrong_outputs": 5}]) == []
    box = tmp_path / "data/mocks"
    box.mkdir()
    (box / "aaaaaaaaaaaa.json").write_text("[1]", encoding="utf-8")
    (box / "bbbbbbbbbbbb.json").write_text("{bad", encoding="utf-8")
    (box / "cccccccccccc.json").write_text(
        json.dumps({"private": [{"drill": "d1"}, {"id": "x"}]}), encoding="utf-8"
    )
    assert mock_store.seen_drills() == {"d1"}
    with pytest.raises(RequestError):
        mock_store.load("aaaaaaaaaaaa")
    with pytest.raises(RequestError):
        mock_store.load("bbbbbbbbbbbb")


def test_only_the_newest_mocks_are_kept(tmp_path: Path) -> None:
    for n in range(mock_store.KEEP + 3):
        mock_store.save({"id": f"{n:012x}"})
    assert len(list((tmp_path / "data/mocks").glob("*.json"))) == mock_store.KEEP


@needs_bwrap
def test_a_model_answer_that_is_not_a_list_gives_no_questions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mock_mcq, "ask_model", lambda *_: {"questions": "no"})
    assert asyncio.run(mock_mcq.generate()) == []
