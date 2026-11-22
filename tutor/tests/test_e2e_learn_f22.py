# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""scripts/e2e_learn.py F22 check: it passes whether or not the tutor ends the card."""

from __future__ import annotations

import importlib
from pathlib import Path
import sys
from typing import Any

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


@pytest.fixture
def learn(monkeypatch: pytest.MonkeyPatch) -> Any:
    """``e2e_learn`` imported from scripts/, as e2e_drive.py runs it."""
    monkeypatch.syspath_prepend(str(SCRIPTS))
    monkeypatch.delitem(sys.modules, "e2e_learn", raising=False)
    return importlib.import_module("e2e_learn")


class FakeFlow:
    """The few Flow calls f22_check makes; ``done`` is module_state's verdict."""

    def __init__(self, done: list[bool | None]) -> None:
        self.done = done
        self.taps: list[str] = []

    def step(self, text: str) -> None:
        """Print nothing."""

    def note(self, text: str) -> None:
        """Print nothing."""

    def result_of(self, rid: str) -> dict[str, Any]:
        return {"ok": True}

    def screen(self, route: str) -> None:
        """No browser."""

    def expect(self, label: str, timeout: float) -> None:
        """No browser."""

    def rids(self) -> set[str]:
        return set()

    def tap(self, label: str, timeout: float = 0) -> None:
        self.taps.append(label)
        self.done.append(True)  # the tap writes the done row

    def request(self, kind: str, before: set[str]) -> str:
        return "r1"

    def result(self, kind: str, before: set[str]) -> dict[str, Any]:
        return {"ok": True}


def _wire(learn: Any, monkeypatch: pytest.MonkeyPatch, flow: FakeFlow) -> None:
    monkeypatch.setattr(learn, "credit_paid", lambda _flow, _state: None)
    monkeypatch.setattr(learn, "module_done", lambda _flow: flow.done[-1])
    monkeypatch.setattr(learn.time, "sleep", lambda _s: None)


def test_check_taps_mark_card_done_when_the_card_is_open(
    learn: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    flow = FakeFlow([None])
    _wire(learn, monkeypatch, flow)
    learn.f22_check(flow, {"rid": "r0", "ledger": [], "sid": "s"})
    assert flow.taps == ["Mark card done"]


def test_check_passes_when_the_tutor_ended_the_card_itself(
    learn: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    flow = FakeFlow([True])
    _wire(learn, monkeypatch, flow)
    learn.f22_check(flow, {"rid": "r0", "ledger": [], "sid": "s"})
    assert flow.taps == []


def test_send_refuses_a_module_done_before_the_flow(
    learn: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    flow = FakeFlow([True])
    _wire(learn, monkeypatch, flow)
    monkeypatch.setattr(learn, "seed", lambda _flow: {"card": "c"})
    monkeypatch.setattr(learn, "transcripts", lambda _flow: set())
    with pytest.raises(learn.FlowError, match="done before the flow"):
        learn.f22_send(flow)
