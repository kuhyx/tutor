# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``session_start`` without a subject teaches Home's pick (``prefs``)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tutor.tests._cur import card, make_ctx, module, subject
from tutor.tests._fakes import turn
from tutor.tests._relay_support import engine
from tutor.tests.test_relay_lanes import Rig, run

if TYPE_CHECKING:
    from pathlib import Path

PICK = "tutor/v1/prefs/current_subject"


def _car(root: Path) -> None:
    ctx, _ = make_ctx(root)
    found = {f"c{i}": card("a", i) for i in range(3)}
    subject(ctx, modules=[module("a", status="ready")], found=found)


@pytest.mark.parametrize(
    ("pick", "want"),
    [
        ("car", "car"),  # Home's pick wins over the live subject
        (None, "automation"),  # nothing picked: the live subject
        ("Not A Slug", "automation"),  # junk in prefs is ignored
        (7, "automation"),
    ],
)
def test_start_without_subject_uses_home_pick(
    tmp_path: Path, pick: object, want: str
) -> None:
    eng, _ = engine(tmp_path, turn("Q1?"))
    _car(tmp_path / "data")

    async def script(rig: Rig) -> None:
        if pick is not None:
            rig.fake.set(PICK, pick)
        got = await rig.send("session_start", {"subject": None, "card": None})
        assert got["ok"], got
        assert eng.source.subject == want

    run(eng, script)


def test_an_explicit_subject_beats_home_pick(tmp_path: Path) -> None:
    eng, _ = engine(tmp_path, turn("Q1?"))
    _car(tmp_path / "data")

    async def script(rig: Rig) -> None:
        rig.fake.set(PICK, "car")
        got = await rig.send("session_start", {"subject": "automation", "card": None})
        assert got["ok"], got
        assert eng.source.subject == "automation"

    run(eng, script)


def test_resume_continues_the_picked_subjects_session(tmp_path: Path) -> None:
    # kuhy, 2026-10-12: live was a car session; Continue in automation must
    # not open it. The automation session is resumed instead.
    eng, _ = engine(tmp_path, turn("Q1?"), turn("Q2?"), turn("Q3?"))
    _car(tmp_path / "data")

    async def script(rig: Rig) -> None:
        first = await rig.send("session_start", {"subject": "automation"})
        assert first["ok"], first
        auto = first["data"]["session"]
        car = await rig.send("session_start", {"subject": "car", "card": None})
        assert car["ok"], car
        assert eng.source.subject == "car"
        rig.fake.set(PICK, "automation")
        back = await rig.send("session_start", {"subject": None, "resume": True})
        assert back["data"] == {"session": auto}
        assert eng.source.subject == "automation"
        again = await rig.send(
            "session_start", {"subject": "automation", "resume": True}
        )
        assert again["data"] == {"session": auto}  # already live: unchanged

    run(eng, script)


def test_resume_with_nothing_open_starts_the_next_card(tmp_path: Path) -> None:
    eng, _ = engine(tmp_path, turn("Q1?"))
    _car(tmp_path / "data")

    async def script(rig: Rig) -> None:
        got = await rig.send("session_start", {"subject": "car", "resume": True})
        assert got["ok"], got
        assert (eng.source.subject, eng.card and eng.card.id) == ("car", "c0")
        bad = await rig.send("session_start", {"subject": "car", "resume": "yes"})
        assert bad["code"] == "bad_request"

    run(eng, script)
