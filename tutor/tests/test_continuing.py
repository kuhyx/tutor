# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Continue respects the subject: the subject's open session, never another's."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

import pytest

from tutor.continuing import open_session
from tutor.curriculum.errors import RequestError
from tutor.engine import Engine
from tutor.store import Store
from tutor.tests._cur import card, make_ctx, module, subject
from tutor.tests._fakes import FakeSession, ManualClock, turn

if TYPE_CHECKING:
    from pathlib import Path

T0 = 1_800_000_000.0


def _write(
    root: Path, sid: str, subj: str | None, card_id: str, *, stopped: bool = False
) -> None:
    start: dict[str, Any] = {"type": "start", "card": card_id, "t": T0}
    if subj is not None:
        start["subject"] = subj
    body = {"message": "Q?", "low_effort": False, "check": None, "check_result": None}
    events = [start, {"type": "tutor", "t": T0 + 1, "turn": body}]
    if stopped:
        events.append({"type": "stop"})
    (root / "sessions").mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(e) + "\n" for e in events)
    (root / "sessions" / f"{sid}.jsonl").write_text(text, encoding="utf-8")


def _pick(root: Path, subj: str, done: dict[str, dict[str, Any]] | None = None) -> str:
    found = open_session(root / "sessions", subj, done or {})
    return found.stem if found else ""


def test_only_the_subjects_newest_session_is_continued(tmp_path: Path) -> None:
    assert _pick(tmp_path, "car") == ""  # no sessions dir yet
    _write(tmp_path, "20261012-100000-aaaa", "automation", "a1")
    _write(tmp_path, "20261012-110000-bbbb", "car", "c1")
    _write(tmp_path, "20261012-120000-cccc", "automation", "a2", stopped=True)
    (tmp_path / "sessions" / "notes.jsonl").write_text("{}\n", encoding="utf-8")
    (tmp_path / "sessions" / "20261012-130000-dddd.jsonl").write_text(
        json.dumps({"type": "start", "card": "x", "subject": "car", "t": T0}) + "\n",
        encoding="utf-8",
    )  # nothing said yet: not resumable
    # The newest automation session was stopped: Continue = the next card,
    # never the older abandoned one.
    assert _pick(tmp_path, "automation") == ""
    _write(tmp_path, "20261012-140000-eeee", "automation", "a3")
    assert _pick(tmp_path, "automation") == "20261012-140000-eeee"
    assert _pick(tmp_path, "car") == "20261012-110000-bbbb"
    assert _pick(tmp_path, "garden") == ""


def test_a_card_taught_elsewhere_since_is_stale(tmp_path: Path) -> None:
    # Live data had this: an unstopped automation session on a card a later
    # session taught. It must not come back.
    _write(tmp_path, "20261011-170448-5b71", None, "a1")
    elsewhere = {"a1": {"session": "20261012-090000-eeee"}}
    assert _pick(tmp_path, "automation", elsewhere) == ""
    here = {"a1": {"session": "20261011-170448-5b71"}}  # Next card / Stop here
    assert _pick(tmp_path, "automation", here) == "20261011-170448-5b71"


def _engine(root: Path, fake: FakeSession) -> Engine:
    return Engine(
        store=Store(root), now=ManualClock(T0), session_factory=lambda _p: fake
    )


def _car(root: Path) -> None:
    ctx, _ = make_ctx(root)
    found = {f"c{i}": card("a", i) for i in range(3)}
    subject(ctx, modules=[module("a", status="ready")], found=found)


def test_engine_continues_the_subject_it_is_asked_for(tmp_path: Path) -> None:
    _car(tmp_path)
    _write(tmp_path, "20261012-100000-aaaa", "car", "c1")
    engine = _engine(tmp_path, FakeSession(turn()))
    assert not asyncio.run(engine.continue_subject(None))  # nothing live
    asyncio.run(engine.start(subject="automation"))
    live = engine.session_id
    assert asyncio.run(engine.continue_subject("automation"))
    assert asyncio.run(engine.continue_subject(None))
    assert engine.session_id == live
    assert asyncio.run(engine.continue_subject("car"))
    assert (engine.session_id, engine.source.subject) == ("20261012-100000-aaaa", "car")
    with pytest.raises(RequestError):
        asyncio.run(engine.continue_subject("garden"))


def test_engine_reports_nothing_to_continue(tmp_path: Path) -> None:
    _car(tmp_path)
    _write(tmp_path, "20261012-100000-aaaa", "car", "c1", stopped=True)
    engine = _engine(tmp_path, FakeSession(turn()))
    asyncio.run(engine.start(subject="automation"))
    assert not asyncio.run(engine.continue_subject("car"))
    assert engine.source.subject == "automation"
