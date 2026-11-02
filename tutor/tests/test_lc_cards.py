# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from tutor import sources
from tutor.curriculum.context import Context
from tutor.relay import lc_cards
from tutor.relay.errors import RequestError
from tutor.store import data_dir
from tutor.tests import _lc_support as s

if TYPE_CHECKING:
    from pathlib import Path

GOOD = {"mechanism_ok": True, "missing": "", "retired": False}
PROPOSAL = {"name": "sentinel", "aliases": [], "properties": ["ordered"]}


@pytest.fixture
def cur(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Context:
    monkeypatch.setattr(sources, "CACHE_DIR", tmp_path / "src-cache")
    return Context(data_dir())


def done_session(monkeypatch: pytest.MonkeyPatch) -> tuple[s.Fakes, str]:
    fakes = s.install(monkeypatch)
    lc_id = s.open_session(fakes)
    s.gated_open(fakes, lc_id)
    s.call("lc_run", {"lc_id": lc_id, "lang": "python3", "code": "def f(): 1"})
    fakes.replies.append(GOOD)
    s.turn(lc_id, "It cancels pairs.", "solved")
    fakes.prompts.clear()
    return fakes, lc_id


def cards(lc_id: str, cur: Context, **body: Any) -> dict[str, Any]:
    return s.call("lc_cards", {"lc_id": lc_id, **body}, cur)


def test_cards_need_a_finished_exit(
    monkeypatch: pytest.MonkeyPatch, cur: Context
) -> None:
    fakes = s.install(monkeypatch)
    lc_id = s.open_session(fakes)
    with pytest.raises(RequestError, match="finish the exit"):
        cards(lc_id, cur)


def test_known_entries_become_cards_in_fsrs_and_anki(
    monkeypatch: pytest.MonkeyPatch, cur: Context
) -> None:
    fakes, lc_id = done_session(monkeypatch)
    fakes.replies.append(
        {"entries": ["xor", "nothing", "XOR", "^"], "proposals": [PROPOSAL]}
    )
    got = cards(lc_id, cur)
    assert [c["back"] for c in got["cards"]] == ["XOR"]
    assert got["cards"][0]["front"] == "Toolbox: self-inverse, order-free?"
    assert got["cards"][0]["new"] is True
    assert got["proposals"] == [PROPOSAL]
    assert got["fsrs"] == {"added": 1, "existing": 0}
    assert got["anki"] == {"delivered": True, "line": "1 cards -> Anki"}
    assert fakes.anki[0] == [
        {"front": "Toolbox: self-inverse, order-free?", "back": "XOR"}
    ]
    assert "postmortem" in fakes.events()
    stored = cur.subjects.cards(lc_lib_subject())
    assert [c.back for c in stored.values()] == ["XOR"]
    meta = cur.subjects.meta(lc_lib_subject())
    assert meta is not None
    assert meta.status == "active"


def lc_lib_subject() -> str:
    return lc_cards.SUBJECT


def test_a_second_run_updates_never_duplicates(
    monkeypatch: pytest.MonkeyPatch, cur: Context
) -> None:
    fakes, lc_id = done_session(monkeypatch)
    for _ in range(2):
        fakes.replies.append({"entries": ["XOR"], "proposals": []})
        got = cards(lc_id, cur)
    assert got["fsrs"] == {"added": 0, "existing": 1}
    assert got["cards"][0]["new"] is False
    assert len(cur.subjects.cards(lc_cards.SUBJECT)) == 1


def test_bad_proposals_are_dropped(
    monkeypatch: pytest.MonkeyPatch, cur: Context
) -> None:
    fakes, lc_id = done_session(monkeypatch)
    fakes.replies.append(
        {
            "entries": [],
            "proposals": [
                {"name": "x", "aliases": [], "properties": ["invented"]},
                {"name": "x", "aliases": [], "properties": []},
                {"name": "XOR", "aliases": [], "properties": ["lookup"]},
            ],
        }
    )
    got = cards(lc_id, cur)
    assert (got["proposals"], got["cards"]) == ([], [])
    assert got["anki"] == {"delivered": False, "line": "no cards"}


def test_confirmed_entries_are_appended_then_carded(
    monkeypatch: pytest.MonkeyPatch, cur: Context
) -> None:
    fakes, lc_id = done_session(monkeypatch)
    got = cards(lc_id, cur, confirm=[PROPOSAL])
    assert fakes.appended == [("sentinel", [], ["ordered"])]
    assert [c["back"] for c in got["cards"]] == ["sentinel"]
    assert not fakes.prompts


def test_a_refused_entry_names_the_reason(
    monkeypatch: pytest.MonkeyPatch, cur: Context
) -> None:
    fakes, lc_id = done_session(monkeypatch)
    fakes.append_error = ValueError("property set nests with 'XOR'")
    got = cards(lc_id, cur, confirm=[PROPOSAL])
    assert got["refused"] == [
        {"name": "sentinel", "reason": "property set nests with 'XOR'"}
    ]
    assert got["cards"] == []


def test_anki_down_is_reported_not_raised(
    monkeypatch: pytest.MonkeyPatch, cur: Context
) -> None:
    fakes, lc_id = done_session(monkeypatch)
    fakes.anki_error = OSError("Anki is closed")
    fakes.replies.append({"entries": ["XOR"], "proposals": []})
    got = cards(lc_id, cur)
    assert got["anki"] == {"delivered": False, "line": "Anki is closed"}
    assert got["fsrs"]["added"] == 1
