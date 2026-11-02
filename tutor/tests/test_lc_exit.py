# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
from __future__ import annotations

import pytest

from tutor.relay import lc_state
from tutor.relay.errors import RequestError
from tutor.tests import _lc_support as s

GOOD = {"mechanism_ok": True, "missing": "", "retired": False}
MISS = {"mechanism_ok": False, "missing": "the NULL step", "retired": False}
EXPLAIN = "It cancels pairs. The rest is left."


def solved_session(
    monkeypatch: pytest.MonkeyPatch, belief: str = ""
) -> tuple[s.Fakes, str]:
    fakes = s.install(monkeypatch)
    lc_id = s.open_session(fakes)
    s.gated_open(fakes, lc_id)
    s.call("lc_run", {"lc_id": lc_id, "lang": "python3", "code": "def f(): 1"})
    if belief:
        state = s.stored(lc_id)
        state["belief"] = belief
        lc_state.save(lc_id, state, 1)
    fakes.prompts.clear()
    return fakes, lc_id


def test_solved_is_held_until_a_run_passed_or_reveal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fakes = s.install(monkeypatch)
    lc_id = s.open_session(fakes)
    got = s.turn(lc_id, EXPLAIN, "solved")
    assert got["held"] is True
    assert "run your solution" in got["note"]
    fakes.replies.append(s.reply("Step one. What is a?"))
    s.turn(lc_id, "reveal")
    fakes.replies.append(GOOD)
    assert s.turn(lc_id, EXPLAIN, "solved")["exit"]["ok"] is True


def test_solved_is_allowed_when_the_examples_cannot_run_locally(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fakes = s.install(monkeypatch)
    lc_id = s.open_session(fakes)
    s.gated_open(fakes, lc_id)
    fakes.run_report = {"ok": True, "no_examples": True}
    s.call("lc_run", {"lc_id": lc_id, "lang": "python3", "code": "x"})
    fakes.replies.append(GOOD)
    assert s.turn(lc_id, EXPLAIN, "solved")["state"]["phase"] == "done"


def test_a_long_explanation_is_held(monkeypatch: pytest.MonkeyPatch) -> None:
    fakes, lc_id = solved_session(monkeypatch)
    got = s.turn(lc_id, "One. Two. Three. Four.", "solved")
    assert got["held"] is True
    assert "at most 2 sentences" in got["note"]
    assert not fakes.prompts


def test_a_right_explanation_closes_with_the_summary_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fakes, lc_id = solved_session(monkeypatch)
    fakes.replies.append(GOOD)
    got = s.turn(lc_id, EXPLAIN, "solved")
    assert got["state"]["phase"] == "done"
    assert got["state"]["exit"]["step"] == "done"
    table = got["exit"]["summary_md"]
    assert table.startswith("| step | what you showed | rung used |")
    assert "| Code | 1 run(s), passing | none |" in table
    assert "| Belief | none recorded |" in table
    assert "session_end" in fakes.events()
    assert s.stored(lc_id)["thread"][-1]["md"] == table
    with pytest.raises(RequestError, match="finished"):
        s.turn(lc_id, "more")


def test_a_missing_mechanism_gets_one_more_turn_then_partial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fakes, lc_id = solved_session(monkeypatch)
    fakes.replies += [MISS, s.reply("What happens to the other months?")]
    first = s.turn(lc_id, EXPLAIN, "solved")
    assert first["exit"] == {"ok": False, "missing": "the NULL step"}
    assert "the NULL step" in fakes.prompts[-1]
    assert first["state"]["phase"] == "exit"
    fakes.replies += [MISS, s.reply("And the other months?")]
    s.turn(lc_id, EXPLAIN, "solved")
    fakes.replies.append(MISS)
    last = s.turn(lc_id, EXPLAIN, "solved")
    assert last["state"]["phase"] == "done"
    assert "mechanism missing after 3 tries" in last["exit"]["summary_md"]


def test_the_opening_belief_is_quoted_and_closed_by_kuhys_correction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fakes, lc_id = solved_session(monkeypatch, belief="sorting always helps")
    fakes.replies += [GOOD, s.reply("You opened with sorting always helps. Why not?")]
    first = s.turn(lc_id, EXPLAIN, "solved")
    assert first["state"]["exit"]["step"] == "belief"
    assert first["exit"] == {"ok": True, "belief": "sorting always helps"}
    assert "sorting always helps" in fakes.prompts[-1]
    fakes.replies.append({**GOOD, "retired": True})
    done = s.turn(lc_id, "Sorting costs more than a map.", "solved")
    assert done["state"]["phase"] == "done"
    assert "| Belief | corrected |" in done["exit"]["summary_md"]


def test_an_unretired_belief_stays_open_after_three_tries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fakes, lc_id = solved_session(monkeypatch, belief="sorting always helps")
    fakes.replies += [GOOD, s.reply("Why not?")]
    s.turn(lc_id, EXPLAIN, "solved")
    for _ in range(2):
        fakes.replies += [GOOD, s.reply("Why not, then?")]
        assert s.turn(lc_id, "Still unsure.", "solved")["state"]["phase"] == "exit"
    fakes.replies.append(GOOD)
    last = s.turn(lc_id, "No idea.", "solved")
    assert "| Belief | still open |" in last["exit"]["summary_md"]
    assert last["state"]["phase"] == "done"


def test_reaching_exit_stamps_exit_ms_for_the_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fakes, lc_id = solved_session(monkeypatch)
    assert "exit_ms" not in s.stored(lc_id)
    fakes.replies.append(GOOD)
    s.turn(lc_id, EXPLAIN, "solved")
    assert s.stored(lc_id)["exit_ms"] == int(s.NOW * 1000)


def test_a_reveal_stamps_exit_ms_too(monkeypatch: pytest.MonkeyPatch) -> None:
    fakes = s.install(monkeypatch)
    lc_id = s.open_session(fakes)
    fakes.replies.append(s.reply("Step one. What is a?"))
    s.turn(lc_id, "reveal")
    assert s.stored(lc_id)["exit_ms"] == int(s.NOW * 1000)
