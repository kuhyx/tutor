# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``python -m tutor migrate``: deck -> subject, done -> taught, idempotent."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from tutor import __main__ as tutor_main
from tutor import cards
from tutor.curriculum import migrate
from tutor.curriculum.eventlog import EventLog
from tutor.curriculum.subject_store import SubjectStore, write_json

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _progress(root: Path) -> None:
    write_json(
        root / "progress.json",
        {
            "cards_done": {
                "fund-plc-definition": {
                    "at": "2026-10-10T12:00:00+00:00",
                    "session": "s1",
                },
                "fund-scan-cycle-order": {"at": "not a date"},
                "not-in-deck": {"at": "2026-10-10T12:00:00+00:00"},
                "fund-modular-rack": "odd",
            },
            "mastered": {
                "relay": {
                    "at": "2026-10-10T12:00:00+00:00",
                    "card": "x",
                    "session": "s1",
                },
                "odd": 1,
            },
        },
    )


def test_migrate_creates_the_subject_and_is_idempotent(tmp_path: Path) -> None:
    _progress(tmp_path)
    first = migrate.migrate(tmp_path, now=5)
    assert first == {
        "subject": "created",
        "modules": 7,
        "cards": 167,
        "taught_added": 2,
        "taught_total": 2,
        "concepts_added": 1,
        "concepts_total": 1,
    }
    again = migrate.migrate(tmp_path, now=6)
    assert again == {**first, "subject": "kept", "taught_added": 0, "concepts_added": 0}
    store = SubjectStore(tmp_path)
    plan = store.plan("automation")
    assert plan is not None
    assert (plan.status, plan.rev) == ("approved", 1)
    assert [m.id for m in plan.modules][:3] == ["fundamentals", "languages", "ladder"]
    assert plan.modules[3].prefixes == ["st-", "sfc-"]
    assert all(m.status == "ready" for m in plan.modules)
    found = store.cards("automation")
    assert found["fund-plc-definition"].origin == "seed"
    events = {e["c"]: e for e in EventLog(tmp_path).read()}
    assert events["fund-plc-definition"]["at"] == 1_791_633_600_000
    assert events["fund-plc-definition"]["session"] == "s1"
    assert events["fund-scan-cycle-order"]["at"] == 5
    assert "session" not in events["fund-scan-cycle-order"]
    assert store.concepts("automation")[0]["name"] == "relay"
    assert json.loads(
        (tmp_path / "subjects/automation/profile.json").read_text(encoding="utf-8")
    )["diagrams"]


def test_a_backward_cross_topic_require_becomes_a_module_require(
    tmp_path: Path,
) -> None:
    deck = cards.load_deck(migrate.DECK_DIR)
    ladder = next(c for c in deck if c.topic.stem == "ladder")
    patched = [
        c
        if c is not ladder
        else cards.Card(**{**c.__dict__, "requires": ("fund-plc-definition",)})
        for c in deck
    ]
    plan, _ = migrate.seed(patched, 1)
    assert [m.requires for m in plan.modules if m.id == "ladder"] == [["fundamentals"]]
    late = next(c for c in deck if c.topic.stem == "fundamentals")
    broken = [
        c if c is not late else cards.Card(**{**c.__dict__, "requires": (ladder.id,)})
        for c in deck
    ]
    plan, _ = migrate.seed(broken, 1)
    assert plan.modules[0].requires == []


def test_cli_dispatch(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert tutor_main.main(["migrate", "--data", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)["cards"] == 167


def test_cli_default_data_dir(capsys: pytest.CaptureFixture[str]) -> None:
    assert migrate.main([]) == 0
    assert json.loads(capsys.readouterr().out)["subject"] == "created"
