# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Which coach turns back the focus timer (``lc_reply.turn_counts``)."""

from __future__ import annotations

import pytest

from tutor.relay import lc_reply
from tutor.tests import _lc_support as s

BEAT = {"source": "tutor", "kind": "heartbeat"}


@pytest.mark.parametrize(
    ("text", "intent", "out", "want"),
    [
        ("ok", "chat", {}, False),
        ("?", "chat", {}, False),
        ("  ok  " + " " * 30, "chat", {}, False),
        ("x" * 19, "chat", {}, False),
        ("x" * 20, "chat", {}, True),
        ("hint", "chat", {}, True),
        ("Hint!", "chat", {}, True),
        (" reveal ", "chat", {}, True),
        ("write it", "chat", {}, True),
        ("ok", "solved", {}, True),
        ("x" * 40, "chat", {"held": True}, False),
        ("hint", "solved", {"held": True}, False),
    ],
)
def test_turn_counts(
    text: str, intent: str, out: dict[str, object], want: bool
) -> None:
    assert lc_reply.turn_counts(text, intent, out) is want


def test_a_one_word_turn_does_not_beat(monkeypatch: pytest.MonkeyPatch) -> None:
    fakes = s.install(monkeypatch)
    lc_id = s.open_session(fakes)
    fakes.fp.activity.clear()
    fakes.replies.append(s.reply("Which part is unclear?"))
    assert s.turn(lc_id, "ok")["reply_md"] == "Which part is unclear?"
    assert fakes.fp.activity == []
    fakes.replies.append(s.reply("Say more about pairs."))
    s.turn(lc_id, "I think it is about pairs of numbers")
    assert fakes.fp.activity == [BEAT]


def test_a_held_run_does_not_beat(monkeypatch: pytest.MonkeyPatch) -> None:
    fakes = s.install(monkeypatch)
    lc_id = s.open_session(fakes)
    fakes.fp.activity.clear()
    got = s.call("lc_run", {"lc_id": lc_id, "lang": "python3", "code": "x"})
    assert got["held"] is True
    assert fakes.fp.activity == []
