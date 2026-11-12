# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The worker's phone-prep report: plan, due cards and the phone's last presence."""

from __future__ import annotations

import asyncio
from dataclasses import replace
import logging
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from tutor import focus_hook
from tutor.relay import phone_check
from tutor.tests._cur import D, H, taught
from tutor.tests._interview_support import install, naive
from tutor.tests._phone_support import (
    NOW_MS,
    PHONE,
    STAMP,
    WEB,
    Rig,
    interview_fp,
    write_plan,
)

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.tests._fake_fp_interview import FakeInterviewFp


@pytest.fixture
def fp(monkeypatch: pytest.MonkeyPatch) -> FakeInterviewFp:
    return interview_fp(install(monkeypatch))


@pytest.fixture
def rig(tmp_path: Path, fp: FakeInterviewFp) -> Rig:
    return Rig(tmp_path, fp)


def tick(rig: Rig) -> None:
    asyncio.run(rig.check.tick())


def test_a_report_carries_plan_due_cards_and_the_phones_last_seen(rig: Rig) -> None:
    write_plan()
    taught(rig.cur, "hosting", "c0", NOW_MS - 10 * D, 0)  # long overdue
    rig.presence(NOW_MS - H)
    rig.fake.set(
        f"tutor/v1-e2e/presence/clients/{WEB}", {"platform": "web", "seen": NOW_MS}
    )
    tick(rig)
    (args,) = rig.reports()
    assert (args["project"], args["milestone"], args["kind"]) == (
        "codility",
        "phone",
        "phone_check",
    )
    assert args["value"] == {"plan": True, "due": 1, "seen_ms": NOW_MS - H}
    assert args["now"] == STAMP
    assert ("run_checks", {"project": "codility", "now": STAMP}) in rig.fp.calls


def test_no_plan_no_due_cards_and_no_phone_report_zeros_and_warn(
    rig: Rig, caplog: pytest.LogCaptureFixture
) -> None:
    write_plan(steps=False)
    with caplog.at_level(logging.WARNING):
        tick(rig)
    (args,) = rig.reports()
    assert args["value"] == {"plan": False, "due": 0, "seen_ms": 0}
    assert "presence" in caplog.text


@pytest.mark.parametrize(
    "node",
    [
        {"platform": "web", "seen": 5},
        {"platform": "android"},
        {"platform": "android", "seen": True},
        {"platform": "android", "seen": "x"},
        "junk",
    ],
)
def test_presence_without_a_usable_phone_reads_as_never_seen(
    rig: Rig, node: object, caplog: pytest.LogCaptureFixture
) -> None:
    rig.fake.set(f"tutor/v1-e2e/presence/clients/{PHONE}", node)
    with caplog.at_level(logging.WARNING):
        tick(rig)
    assert rig.reports()[0]["value"]["seen_ms"] == 0
    assert "presence" in caplog.text


def test_the_newest_of_several_phones_wins(rig: Rig) -> None:
    rig.presence(1000)
    rig.fake.set(
        f"tutor/v1-e2e/presence/clients/{WEB}", {"platform": "android", "seen": 2000}
    )
    tick(rig)
    assert rig.reports()[0]["value"]["seen_ms"] == 2000


def test_unreadable_presence_fails_closed_with_a_warning(
    rig: Rig, caplog: pytest.LogCaptureFixture
) -> None:
    rig.fake.fail[("GET", "/presence/clients")] = 503
    with caplog.at_level(logging.WARNING):
        tick(rig)
    assert rig.reports()[0]["value"]["seen_ms"] == 0
    assert "presence" in caplog.text


def test_a_project_with_no_subjects_has_nothing_due(rig: Rig) -> None:
    rig.fp.projects[0] = replace(rig.fp.projects[0], subjects=())
    tick(rig)
    assert rig.reports()[0]["value"]["due"] == 0


def test_repeats_are_rate_limited_unless_the_verdict_changes(rig: Rig) -> None:
    write_plan()
    rig.presence(NOW_MS - H)
    tick(rig)
    rig.now += 60
    rig.presence(NOW_MS)  # seen moved, the verdict did not
    tick(rig)
    assert len(rig.reports()) == 1
    assert sum(1 for n, _ in rig.fp.calls if n == "run_checks") == 2  # still latched
    rig.now += 60
    rig.presence(0)
    tick(rig)  # not fresh any more: the verdict changed
    assert len(rig.reports()) == 2
    rig.now += phone_check.APPEND_EVERY_S  # unchanged but half an hour old
    tick(rig)
    assert len(rig.reports()) == 3


def test_no_interview_no_report(rig: Rig, fp: FakeInterviewFp) -> None:
    fp.projects.clear()
    tick(rig)
    assert fp.calls == []
    fp.create_project(
        "plain",
        name="Plain",
        start=naive(2027, 1, 15).date(),
        end=naive(2027, 1, 20).date(),
        replaces=["tutor"],
        daily_minutes=60,
        unlock_minutes=10,
    )
    tick(rig)
    assert fp.calls == []


def test_without_focus_project_or_with_the_old_one_it_does_nothing(
    rig: Rig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(focus_hook, "load_fp", lambda: None)
    tick(rig)
    monkeypatch.setattr(focus_hook, "load_fp", SimpleNamespace)
    tick(rig)
    assert rig.reports() == []


def test_a_failing_registry_is_logged_and_never_raised(
    rig: Rig, caplog: pytest.LogCaptureFixture
) -> None:
    rig.fp.refuse = ValueError("not an interview project")
    with caplog.at_level(logging.ERROR):
        tick(rig)
    assert "phone check" in caplog.text
