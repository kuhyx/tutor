# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""A spent Claude limit: the whole LeetCode coach runs on the local model."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import pytest

from tutor import local_model, sources, unavailable
from tutor.curriculum import modelcall
from tutor.curriculum.context import Context
from tutor.outage import ClaudeUnavailableError
from tutor.relay import lc_reply
from tutor.relay.errors import RequestError
from tutor.store import data_dir
from tutor.tests import _lc_support as s

if TYPE_CHECKING:
    from pathlib import Path

GOOD = {"mechanism_ok": True, "missing": "", "retired": False}
PROPOSAL = {"name": "sentinel", "aliases": [], "properties": ["ordered"]}


def _never(*_args: object, **_kwargs: object) -> dict[str, Any]:
    """Claude must not be spawned while the outage window is open."""
    msg = "Claude was called during an outage"
    raise AssertionError(msg)


def _outage(monkeypatch: pytest.MonkeyPatch) -> s.Fakes:
    """Real ``ask_or_local`` everywhere, an open window, Ollama = the fake model."""
    fakes = s.install(monkeypatch)
    for module in ("lc_reply", "lc_exit", "lc_cards"):
        monkeypatch.setattr(
            f"tutor.relay.{module}.ask_or_local", modelcall.ask_or_local
        )
    monkeypatch.setattr(modelcall, "ask_model", _never)
    monkeypatch.setattr(local_model, "ask", fakes.model)
    now = time.time()
    unavailable.record("rate_limit", now - 5, now + 600)
    return fakes


def test_open_and_turn_run_on_the_local_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """The opener and a coach turn are answered; the opener names the local model."""
    fakes = _outage(monkeypatch)
    fakes.replies.append(s.reply("Local opener: which part is unclear?"))
    got = s.call("lc_open", {"problem": "https://leetcode.com/problems/two-sum/"})
    assert got["reply_md"] == "Local opener: which part is unclear?"
    assert got["model"] == local_model.MODEL
    lc_id = str(got["lc_id"])
    s.gated_open(fakes, lc_id)
    fakes.replies.append(s.reply("Local hint: what does the map hold?"))
    out = s.turn(lc_id, "I think I need a hash map but why?")
    assert out["reply_md"] == "Local hint: what does the map hold?"


def test_a_session_finishes_and_makes_cards_on_the_local_model(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The exit grade and the post-mortem proposals work while Claude is out."""
    monkeypatch.setattr(sources, "CACHE_DIR", tmp_path / "src-cache")
    fakes = _outage(monkeypatch)
    lc_id = s.open_session(fakes)
    s.gated_open(fakes, lc_id)
    s.call("lc_run", {"lc_id": lc_id, "lang": "python3", "code": "def f(): 1"})
    fakes.replies.append(GOOD)
    done = s.turn(lc_id, "It cancels pairs.", "solved")
    assert done["exit"]["ok"] is True
    assert done["state"]["phase"] == "done"
    fakes.replies.append({"entries": [], "proposals": [PROPOSAL]})
    cards = s.call("lc_cards", {"lc_id": lc_id}, Context(data_dir()))
    assert [p["name"] for p in cards["proposals"]] == ["sentinel"]


def test_open_still_refuses_when_the_local_model_is_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No local model either: the outage is raised as before."""
    _outage(monkeypatch)
    monkeypatch.setattr(local_model, "ask", lambda *_a, **_k: None)
    with pytest.raises(ClaudeUnavailableError):
        s.call("lc_open", {"problem": "https://leetcode.com/problems/two-sum/"})


TWO_SUM = {"problem": "https://leetcode.com/problems/two-sum/"}
PASTED = "def twoSum(nums, target): pass"


def test_a_local_reply_is_rescued_from_its_code_and_extra_questions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The local model pastes the signature: cut out, one ask, no re-ask."""
    fakes = _outage(monkeypatch)
    fakes.replies.append(s.reply(f"Restated. Clear?\n\n{PASTED}\n\nWhich part?"))
    got = s.call("lc_open", TWO_SUM)
    assert got["reply_md"] == "Restated.\n\nWhich part?"
    assert len(fakes.prompts) == 1
    fakes.replies.append(s.reply(f"Restated.\n\n{PASTED}"))
    lc_id = str(got["lc_id"])
    s.gated_open(fakes, lc_id)
    out = s.turn(lc_id, "I think I need a hash map but why?")
    assert out["reply_md"] == f"Restated.\n\n{lc_reply.GENERIC_ASK}"


def test_the_local_model_gets_six_tries(monkeypatch: pytest.MonkeyPatch) -> None:
    """Six local tries (a rescue cannot save a reply that is only code)."""
    fakes = _outage(monkeypatch)
    tries = lc_reply.LOCAL_TRIES
    fakes.replies += [s.reply(PASTED)] * (tries - 1) + [s.reply("Restated. Which?")]
    assert s.call("lc_open", TWO_SUM)["reply_md"] == "Restated. Which?"
    fakes.replies += [s.reply(PASTED)] * tries
    with pytest.raises(RequestError, match="no valid reply"):
        s.call("lc_open", TWO_SUM)
    assert len(fakes.prompts) == 2 * tries
