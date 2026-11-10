# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The tutor credit hook: a heartbeat for focus projects, never an error."""

from __future__ import annotations

from datetime import date
import logging
from typing import TYPE_CHECKING

from tutor import credit, focus_hook, unit_credit
from tutor.clock import BlockReady
from tutor.tests._fake_fp import FakeFp, FakeProject

if TYPE_CHECKING:
    import pytest

NOON = 1_800_000_000.0


def _project(*subjects: str) -> FakeProject:
    day = date.fromisoformat(credit.local_day(NOON)[0])
    return FakeProject("exam", "Exam", day, day, ("tutor",), 60, 10, subjects)


def _use(monkeypatch: pytest.MonkeyPatch, fake: FakeFp | None) -> None:
    monkeypatch.setattr(focus_hook, "load_fp", lambda: fake)


def test_a_listed_subject_beats_the_heart(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeFp([_project("sql")])
    _use(monkeypatch, fake)
    focus_hook.heartbeat("sql", NOON, None)
    assert fake.activity == [{"source": "tutor", "kind": "heartbeat", "ts": None}]


def test_an_unlisted_subject_is_silent(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeFp([_project("sql")])
    _use(monkeypatch, fake)
    focus_hook.heartbeat("automation", NOON, None)
    focus_hook.heartbeat(None, NOON, None)
    assert fake.activity == []


def test_no_active_project_is_silent(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeFp()
    _use(monkeypatch, fake)
    focus_hook.heartbeat("sql", NOON, None)
    assert fake.activity == []


def test_a_missing_package_is_a_no_op(monkeypatch: pytest.MonkeyPatch) -> None:
    _use(monkeypatch, None)
    focus_hook.heartbeat("sql", NOON, None)


def test_any_failure_is_logged_never_raised(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    fake = FakeFp([_project("sql")], boom=RuntimeError("disk on fire"))
    _use(monkeypatch, fake)
    with caplog.at_level(logging.WARNING, logger="tutor.focus_hook"):
        focus_hook.heartbeat("sql", NOON, None)
    assert "disk on fire" in caplog.text


def test_a_failing_import_is_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken() -> object:
        msg = "half-written package"
        raise SyntaxError(msg)

    monkeypatch.setattr(focus_hook, "load_fp", broken)
    focus_hook.heartbeat("sql", NOON, None)


def _unit(n: int) -> BlockReady:
    return BlockReady(n, 60.0 * n, NOON, 2, 3)


def test_credit_units_beats_after_a_recorded_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeFp([_project("sql")])
    _use(monkeypatch, fake)
    rows = unit_credit.credit_units([_unit(1)], "s1", now=NOON, subject="sql")
    assert rows[0]["recorded"]
    assert len(fake.activity) == 1


def test_credit_units_without_a_subject_never_beats(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeFp([_project("sql")])
    _use(monkeypatch, fake)
    unit_credit.credit_units([_unit(1)], "s2", now=NOON)
    assert fake.activity == []


def test_a_failing_hook_leaves_the_credit_intact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeFp([_project("sql")], boom=OSError("full"))
    _use(monkeypatch, fake)
    rows = unit_credit.credit_units([_unit(1)], "s3", now=NOON, subject="sql")
    assert rows[0]["recorded"]


def test_load_fp_is_none_when_absent_and_the_module_when_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("importlib.util.find_spec", lambda _name: None)
    assert focus_hook.load_fp() is None
    sentinel = object()
    monkeypatch.setattr("importlib.util.find_spec", lambda _name: object())
    monkeypatch.setattr("importlib.import_module", lambda _name: sentinel)
    assert focus_hook.load_fp() is sentinel
