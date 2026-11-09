# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
from __future__ import annotations

from typing import TYPE_CHECKING

from tutor.tests import _lc_support as s

if TYPE_CHECKING:
    import pytest


def test_code_is_held_before_the_requirement_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fakes = s.install(monkeypatch)
    lc_id = s.open_session(fakes)
    fakes.prompts.clear()
    fakes.fp.activity.clear()
    got = s.turn(lc_id, "def f(nums):\n    return 1")
    assert (got["held"], "reply_md" in got) == (True, False)
    assert "requirement list" in got["note"]
    assert not fakes.prompts
    assert s.stored(lc_id)["turns"] == 0
    assert fakes.fp.activity == []


def test_plain_chat_is_allowed_in_the_gate_phase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fakes = s.install(monkeypatch)
    lc_id = s.open_session(fakes)
    fakes.replies.append(s.reply("Which part is unclear?"))
    got = s.turn(lc_id, "the problem")
    assert got["reply_md"] == "Which part is unclear?"
    assert got["state"]["turns"]["used"] == 1
    assert got["state"]["phase"] == "gate"


def test_req_list_walks_incomplete_pass_and_forced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fakes = s.install(monkeypatch)
    lc_id = s.open_session(fakes)
    fakes.verdicts += [("incomplete", ("self-inverse",))] * 3
    first = s.turn(lc_id, "req: pairs")
    assert "does not yet say self-inverse; 1 of 3" in first["note"]
    assert first["state"]["gate"]["open"] is False
    s.turn(lc_id, "req: pairs again")
    third = s.turn(lc_id, "req: pairs still")
    assert "code accepted anyway" in third["note"]
    assert third["state"]["gate"]["forced"] is True
    assert third["state"]["phase"] == "work"
    assert fakes.events().count("req_check") == 3
    fakes.replies.append(s.reply("Run it on [3,2,4].\n\nWhat happens?"))
    s.turn(lc_id, "def f(a):\n    return a")
    assert ("two-sum", "code", {"req_incomplete": True}) in fakes.logs
    assert s.stored(lc_id)["reqs"] == [
        "req: pairs",
        "req: pairs again",
        "req: pairs still",
    ]


def test_req_pass_and_unverified_open_the_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    fakes = s.install(monkeypatch)
    lc_id = s.open_session(fakes)
    fakes.verdicts.append(("unverified", ()))
    got = s.turn(lc_id, "req: x")
    assert "unverified" in got["note"]
    assert got["state"]["phase"] == "work"


def test_wrong_gate_prefix_is_held(monkeypatch: pytest.MonkeyPatch) -> None:
    fakes = s.install(monkeypatch)
    lc_id = s.open_session(fakes)
    got = s.turn(lc_id, "shape: id")
    assert got["held"] is True
    assert "start with req:" in got["note"]
    sql = s.install(monkeypatch, s.Fakes(problem=s.SQL))
    sql_id = s.open_session(sql)
    assert "start with shape:" in s.turn(sql_id, "req: id")["note"]


def test_sql_shape_gate_wants_every_output_column(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fakes = s.install(monkeypatch, s.Fakes(problem=s.SQL))
    lc_id = s.open_session(fakes)
    miss = s.turn(lc_id, "shape: one row per id, column id")
    assert "Jan_Revenue" in miss["note"]
    ok = s.turn(lc_id, "shape: columns id and Jan_Revenue, one row per id")
    assert "accepted" in ok["note"]
    assert ok["state"]["gate"]["tries"] == 1
