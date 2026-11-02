# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The hand-written SQL drill pack: coverage of the test topics and the CLI."""

from __future__ import annotations

from collections import Counter
import os
from typing import TYPE_CHECKING, Any

import pytest
import sql_drills as sd

from tutor import __main__ as tutor_main
from tutor.relay import sql
from tutor.sql_pack import SPECS, cli

if TYPE_CHECKING:
    from pathlib import Path

TOPICS = (
    "pivot",
    "dates",
    "number-format",
    "joins-null",
    "group-having",
    "window",
    "strings",
)


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s["title"])
def test_every_spec_is_a_valid_drill_spec(spec: dict[str, Any]) -> None:
    sd.DrillSpec.from_mapping(spec)


def test_every_topic_has_four_drills_of_both_kinds() -> None:
    kinds = Counter((s["topic"], s["kind"]) for s in SPECS)
    for topic in TOPICS:
        assert kinds[topic, "write"] >= 2, topic
        assert kinds[topic, "predict"] >= 1, topic
        assert kinds[topic, "write"] + kinds[topic, "predict"] >= 4, topic


def test_titles_are_unique() -> None:
    titles = [s["title"] for s in SPECS]
    assert len(titles) == len(set(titles))


class FakeSd:
    """Accepts every spec; refuses the first when ``bad`` was pre-saved."""

    class SpecError(ValueError):
        """Stands in for ``sql_drills.SpecError``."""

    def __init__(self) -> None:
        self.running = False
        self.saved: list[str] = []

    def ensure_running(self) -> None:
        self.running = True

    def save_generated(self, spec: dict[str, Any]) -> str:
        if spec["title"] == SPECS[0]["title"] and "bad" in self.saved:
            msg = "empty output"
            raise self.SpecError(msg)
        self.saved.append(spec["title"])
        return f"g-{len(self.saved)}"


def test_cli_saves_every_spec_and_prints_ids(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    fake = FakeSd()
    monkeypatch.setattr(sql, "load_sd", lambda: fake)
    monkeypatch.setattr(cli, "load_sd", lambda: fake)
    monkeypatch.delenv("SQL_DRILLS_DATA", raising=False)
    assert tutor_main.main(["sql-pack", "--data", str(tmp_path)]) == 0
    assert fake.running
    assert len(fake.saved) == len(SPECS)
    assert os.environ["SQL_DRILLS_DATA"] == str(tmp_path)
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == f"g-1 {SPECS[0]['topic']} {SPECS[0]['kind']}"
    monkeypatch.delenv("SQL_DRILLS_DATA")


def test_cli_reports_a_refused_spec_and_exits_1(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeSd()
    fake.saved.append("bad")
    monkeypatch.setattr(cli, "load_sd", lambda: fake)
    assert cli.main([]) == 1
    out = capsys.readouterr().out
    assert f"REFUSED {SPECS[0]['title']}: empty output" in out
    assert len(fake.saved) == len(SPECS)
