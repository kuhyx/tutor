# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Pre-built mocks: stocking, `start` taking one first, the builder and its CLI."""

from __future__ import annotations

import json
import os
import secrets
import time
from typing import TYPE_CHECKING, Any

import pytest

from tutor import __main__ as tutor_main
from tutor.relay import mock_mcq, mock_pool, mock_prebuild, mock_sql, mock_store
from tutor.relay.mock_seeds import SEEDS
from tutor.tests._mock_support import FakeSd, call, install, needs_bwrap

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def sd(monkeypatch: pytest.MonkeyPatch) -> FakeSd:
    fake = install(monkeypatch)

    def no_model(*_: object) -> dict[str, Any]:
        msg = "the model must not be called"
        raise AssertionError(msg)

    monkeypatch.setattr(mock_mcq, "ask_model", no_model)
    monkeypatch.setattr(mock_sql, "ask_model", no_model)
    return fake


def _stock(n: int) -> list[str]:
    ids = [f"{i:012x}" for i in range(1, n + 1)]
    for mock_id in ids:
        mock_pool.stock({"id": mock_id, "tasks": [], "private": [], "answers": {}})
        time.sleep(0.01)
    return ids


def _take() -> dict[str, Any]:
    paper = mock_pool.take()
    assert paper is not None
    return paper


def test_curated_returns_fewer_when_the_bank_is_used_up() -> None:
    every = {s["code"] for s in SEEDS}
    assert mock_mcq.curated(secrets.SystemRandom(), every) == []


def test_take_is_first_in_first_out_and_removes_the_file() -> None:
    assert mock_pool.take() is None
    first, second = _stock(2)
    assert mock_pool.count() == 2
    taken = mock_pool.take()
    assert taken is not None
    assert taken["id"] == first
    assert mock_pool.count() == 1
    taken = mock_pool.take()
    assert taken is not None
    assert taken["id"] == second
    assert mock_pool.take() is None


def test_take_skips_and_deletes_an_unreadable_file(tmp_path: Path) -> None:
    (first,) = _stock(1)
    folder = tmp_path / "data" / "mocks_ready"
    (folder / "bad-a.json").write_text("{not json", encoding="utf-8")
    (folder / "bad-b.json").write_text("[1]", encoding="utf-8")
    for bad in folder.glob("bad-*.json"):
        os.utime(bad, (1, 1))
    assert mock_pool.used()[0] == set()
    taken = mock_pool.take()
    assert taken is not None
    assert taken["id"] == first
    assert not list(folder.glob("*.json"))


@needs_bwrap
def test_prebuilt_papers_are_whole_distinct_and_leak_nothing(sd: FakeSd) -> None:
    del sd
    mock_prebuild.build(3)
    assert mock_pool.count() == 3
    papers = [_take() for _ in range(3)]
    codes = [t["code"] for p in papers for t in p["tasks"] if t["section"] == "py_mcq"]
    assert len(codes) == 30
    assert len(set(codes)) == 30
    for paper in papers:
        sections = [t["section"] for t in paper["tasks"]]
        assert sections == ["py_mcq"] * 10 + ["py_code"] + ["sql"] * 3
        assert len(paper["private"]) == 14
        assert "answers" in paper
    drills = {t["drill"] for p in papers for t in p["private"] if t.get("drill")}
    assert len(drills) >= 3
    palin = [p["private"][10]["palin"] for p in papers]
    assert palin[0] == palin[2] != palin[1]


@needs_bwrap
def test_start_hands_out_a_prebuilt_mock_without_the_model(sd: FakeSd) -> None:
    del sd
    mock_prebuild.build(1)
    ready = mock_pool.count()
    begun = time.perf_counter()
    paper = call({"op": "start", "minutes": 45})
    assert time.perf_counter() - begun < 1.0
    assert ready == 1
    assert mock_pool.count() == 0
    assert paper["minutes"] == 45
    assert paper["deadline_ms"] - paper["started_ms"] == 45 * 60_000
    wire = json.dumps(paper)
    assert "private" not in wire
    assert "correct" not in wire
    stored = mock_store.load(paper["mock_id"])
    assert stored["deadline_ms"] == paper["deadline_ms"]
    assert call({"op": "get", "mock_id": paper["mock_id"]})["tasks"] == paper["tasks"]
    assert len(stored["private"]) == 14


@needs_bwrap
def test_start_falls_back_to_building_when_the_pool_is_empty(
    sd: FakeSd, monkeypatch: pytest.MonkeyPatch
) -> None:
    del sd

    def fake_mcq(system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        del system, prompt, schema
        return {"questions": []}

    monkeypatch.setattr(mock_mcq, "ask_model", fake_mcq)
    monkeypatch.setattr(mock_sql, "ask_model", fake_mcq)
    paper = call({"op": "start"})
    assert len(paper["tasks"]) == 14
    assert mock_pool.count() == 0


@needs_bwrap
def test_prebuild_cli_builds_and_reports(
    sd: FakeSd, capsys: pytest.CaptureFixture[str]
) -> None:
    del sd
    assert tutor_main.main(["mock-prebuild", "2"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert len(out) == 2
    assert all(line.startswith("ready ") for line in out)
    assert mock_pool.count() == 2


def test_prebuild_cli_rejects_a_bad_count(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        tutor_main.main(["mock-prebuild", "0"])
    assert "count" in capsys.readouterr().err
