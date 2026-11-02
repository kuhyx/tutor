# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
from __future__ import annotations

import pytest

from tutor import focus_hook
from tutor.relay import lc_backend, lc_state
from tutor.relay.errors import RequestError
from tutor.tests import _lc_support as s

Q = "What does the lookup return?"


def ready(
    monkeypatch: pytest.MonkeyPatch, problem: lc_backend.Problem = s.ALGO
) -> tuple[s.Fakes, str]:
    fakes = s.install(monkeypatch, s.Fakes(problem=problem))
    lc_id = s.open_session(fakes)
    s.gated_open(fakes, lc_id)
    fakes.prompts.clear()
    return fakes, lc_id


def test_leak_check_bounces_a_reply_naming_an_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fakes, lc_id = ready(monkeypatch)
    fakes.replies += [s.reply("Maybe XOR helps?"), s.reply("What cancels out?")]
    got = s.turn(lc_id, "I am stuck")
    assert got["reply_md"] == "What cancels out?"
    assert "names XOR" in fakes.prompts[-1]
    fakes.replies.append(s.reply("Is XOR what you meant?"))
    ok = s.turn(lc_id, "is it xor?")
    assert ok["reply_md"] == "Is XOR what you meant?"


def test_leak_check_is_off_after_the_first_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fakes, lc_id = ready(monkeypatch)
    fakes.replies.append(s.reply("A hash map would work; does yours?"))
    s.turn(lc_id, "def f(a):\n    return a")
    fakes.replies.append(s.reply("XOR is the idea; why?"))
    assert "XOR" in s.turn(lc_id, "why does it fail")["reply_md"]


def test_one_question_rule_and_model_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fakes, lc_id = ready(monkeypatch)
    fakes.replies += [s.reply("What? Why?")] * 3
    with pytest.raises(RequestError) as caught:
        s.turn(lc_id, "help")
    assert (caught.value.code, caught.value.retry) == ("model_error", True)
    assert s.stored(lc_id)["turns"] == 0
    assert len(s.stored(lc_id)["thread"]) == 3
    fakes.replies += [s.reply(""), s.reply("What now?")]
    assert s.turn(lc_id, "help")["reply_md"] == "What now?"


def test_reply_may_not_write_code_with_the_problems_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fakes, lc_id = ready(monkeypatch)
    fakes.replies += [s.reply("Try `twoSum(nums, 9)`. Why?"), s.reply("What is nums?")]
    assert s.turn(lc_id, "help")["reply_md"] == "What is nums?"
    assert "could paste" in fakes.prompts[-1]


def test_hint_rungs_climb_one_at_a_time_and_are_logged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fakes, lc_id = ready(monkeypatch)
    fakes.replies += [
        s.reply("Pointer one.\n\nWhat is a?", "H3"),
        s.reply("What is a?", "H1"),
    ]
    got = s.turn(lc_id, "hint")
    assert got["state"]["rung"] == "H1"
    assert "climbs too fast" in fakes.prompts[-1]
    assert ("two-sum", "rung", {"rung": "H1"}) in fakes.logs
    fakes.replies.append(s.reply("Same level.", "H1"))
    fakes.replies.append(s.reply("A bit more. What is b?", "H2"))
    assert s.turn(lc_id, "hint")["state"]["rung"] == "H2"
    fakes.replies += [s.reply("What is c?", "H3")] * 2 + [s.reply("What is c?", "")]
    assert s.turn(lc_id, "why")["state"]["rung"] == "H2"
    fakes.replies += [s.reply("What is d?", "bad"), s.reply("What is d?", "H2")]
    s.turn(lc_id, "hint")
    assert "must be H0" in fakes.prompts[-1]


def test_bigger_hint_climbs_two_and_a_failed_run_allows_a_climb(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fakes, lc_id = ready(monkeypatch)
    fakes.replies.append(s.reply("What is a?", "H1"))
    s.turn(lc_id, "hint")
    fakes.replies.append(s.reply("What is b?", "H3"))
    assert s.turn(lc_id, "hint!")["state"]["rung"] == "H3"
    state = s.stored(lc_id)
    state.update(rung=0, failed=True)
    lc_state.save(lc_id, state, 1)
    fakes.replies.append(s.reply("What is c?", "H1"))
    got = s.turn(lc_id, "it fails")
    assert got["state"]["rung"] == "H1"
    assert s.stored(lc_id)["failed"] is False


def test_failed_flag_stays_while_the_rung_does_not_climb(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fakes, lc_id = ready(monkeypatch)
    state = s.stored(lc_id)
    state.update(rung=1, failed=True)
    lc_state.save(lc_id, state, 1)
    fakes.replies.append(s.reply("What is c?", "H1"))
    s.turn(lc_id, "it fails")
    assert s.stored(lc_id)["failed"] is True


def test_budget_banner_and_prompt_note(monkeypatch: pytest.MonkeyPatch) -> None:
    fakes, lc_id = ready(monkeypatch)
    state = s.stored(lc_id)
    state["turns"] = 16
    lc_state.save(lc_id, state, 1)
    fakes.replies.append(s.reply("Summary. Write a full attempt."))
    got = s.turn(lc_id, "more")
    assert got["banner"] == "budget"
    assert got["state"]["turns"] == {"used": 17, "budget": 16, "over": True}
    assert "[app: budget reached]" in fakes.prompts[-1]


def test_frustration_stops_without_a_model_call_and_offers_three_choices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fakes, lc_id = ready(monkeypatch)
    got = s.turn(lc_id, "we are going in circles")
    assert got["choices"] == ["write it", "hint!", "reveal"]
    assert "going in circles" in got["reply_md"]
    assert not fakes.prompts
    fakes.replies.append(s.reply("Which word is unclear?"))
    assert "choices" not in s.turn(lc_id, "I don't understand")
    assert "choices" in s.turn(lc_id, "I don't understand")
    assert s.stored(lc_id)["turns"] == 1


def test_write_it_opens_code_without_a_requirement_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fakes = s.install(monkeypatch)
    lc_id = s.open_session(fakes)
    got = s.turn(lc_id, "write it")
    assert "Paste your whole function" in got["reply_md"]
    assert got["state"]["gate"]["forced"] is True
    assert got["state"]["phase"] == "work"
    assert s.turn(lc_id, "write it")["state"]["phase"] == "work"


def test_reveal_relaxes_the_checks_and_moves_to_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fakes, lc_id = ready(monkeypatch)
    walk = "Line 1 `twoSum(nums, t)` does X. Why? And why?"
    fakes.replies.append(s.reply(walk, "H3"))
    got = s.turn(lc_id, "Reveal")
    assert got["reply_md"] == walk
    assert (got["state"]["revealed"], got["state"]["phase"]) == (True, "exit")
    assert "reveal" in fakes.events()
    assert "walk the solution" in fakes.prompts[-1].lower()
    assert "banner" not in got
    assert got["state"]["rung"] is None


def test_reply_refering_to_the_code_gets_it_reprinted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fakes, lc_id = ready(monkeypatch)
    fakes.replies.append(s.reply("Trace your code on [1]. What happens?"))
    s.turn(lc_id, "def g(v):\n    return v")
    fakes.replies.append(s.reply("Look at your code again. What is v?"))
    got = s.turn(lc_id, "so?")
    assert "Your last attempt" in got["reply_md"]
    assert "def g(v)" in got["reply_md"]


def test_first_stated_belief_is_kept_and_a_done_session_is_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fakes, lc_id = ready(monkeypatch)
    fakes.replies.append(s.reply("Why?", "", "sorting always helps"))
    s.turn(lc_id, "sorting always helps, right?")
    fakes.replies.append(s.reply("Why not?", "", "another belief"))
    s.turn(lc_id, "ok")
    state = s.stored(lc_id)
    assert state["belief"] == "sorting always helps"
    state["phase"] = "done"
    lc_state.save(lc_id, state, 1)
    with pytest.raises(RequestError, match="finished"):
        s.turn(lc_id, "more")
    assert "Recorded opening belief" in fakes.prompts[-1]


def test_second_code_message_is_not_logged_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fakes, lc_id = ready(monkeypatch)
    fakes.replies += [s.reply("What is a?")] * 2
    s.turn(lc_id, "def g(v):\n    return v")
    s.turn(lc_id, "def g(v):\n    return v + 1")
    assert fakes.events().count("code") == 1
    assert s.stored(lc_id)["last_code"].endswith("v + 1")


def test_an_oversized_text_is_rejected_by_the_protocol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(RequestError):
        s.validate("lc_turn", {"lc_id": "a" * 12, "text": "x" * 8001})


def test_heartbeat_without_focus_project_and_list_skips_bad_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fakes = s.install(monkeypatch)
    monkeypatch.setattr(focus_hook, "load_fp", lambda: None)
    lc_id = s.open_session(fakes)
    (lc_state._path(lc_id).parent / "junk.json").write_text("{", encoding="utf-8")
    assert [r["lc_id"] for r in s.call("lc_list", {})["recent"]] == [lc_id]
