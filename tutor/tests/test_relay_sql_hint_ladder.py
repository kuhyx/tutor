# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``sql_hint``: hints graduate from the smallest nudge; no syntax up front."""

from __future__ import annotations

from typing import Any

import pytest

from tutor.relay import sql_model
from tutor.tests._sql_support import FakeSd, call, install_fake_fp, install_fake_sd

NUDGE = "Which rule decides how many decimals a number keeps in the output?"
LATER = "Is there a function that fixes the number of decimals?"


class FakeModel:
    def __init__(self, *answers: dict[str, Any]) -> None:
        self.answers = list(answers)
        self.prompts: list[tuple[str, str]] = []

    def __call__(self, system: str, prompt: str, schema: dict[str, Any]) -> Any:
        del schema
        self.prompts.append((system, prompt))
        return self.answers.pop(0)


def model(monkeypatch: pytest.MonkeyPatch, *answers: dict[str, Any]) -> FakeModel:
    fake = FakeModel(*answers)
    monkeypatch.setattr(sql_model, "ask_model", fake)
    return fake


@pytest.fixture
def sd(monkeypatch: pytest.MonkeyPatch) -> FakeSd:
    install_fake_fp(monkeypatch)
    return install_fake_sd(monkeypatch)


@pytest.mark.parametrize(
    "leak",
    [
        "Would ROUND help with the decimals?",
        "Have you tried CAST for the number format?",
        "What does FORMAT do to a number?",
        "Which function, say avg(x), fixes the scale?",
        "Could IFNULL or COALESCE cover the missing phone?",
    ],
)
def test_the_first_hint_names_no_function_or_syntax(
    sd: FakeSd, monkeypatch: pytest.MonkeyPatch, leak: str
) -> None:
    fake = model(monkeypatch, {"question": leak}, {"question": NUDGE})
    got = call("sql_hint", {"id": "q1", "sql": "SELECT AVG(amount) FROM o"})
    assert got == {"question": NUDGE}
    assert "function or syntax" in fake.prompts[1][1]
    assert not any(w in got["question"].upper() for w in ("ROUND", "CAST", "FORMAT"))


def test_the_ladder_is_in_both_the_system_and_the_user_prompt(
    sd: FakeSd, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = model(monkeypatch, {"question": NUDGE}, {"question": LATER})
    call("sql_hint", {"id": "q1"})
    system, first = fake.prompts[0]
    assert "smallest nudge" in system
    assert "Hint level 1" in first
    call("sql_hint", {"id": "q1", "history": [NUDGE]})
    assert "Hint level 2" in fake.prompts[1][1]


def test_a_later_hint_may_name_the_function(
    sd: FakeSd, monkeypatch: pytest.MonkeyPatch
) -> None:
    ask = "Would ROUND be the right tool for the decimals?"
    model(monkeypatch, {"question": ask})
    got = call("sql_hint", {"id": "q1", "history": [NUDGE, LATER]})
    assert got == {"question": ask}


def test_lesson_probes_graduate_too() -> None:
    from tutor.relay import sql_lesson_prompt as prompt

    assert "smallest nudge" in prompt.SYSTEM
    assert "never name a function or syntax" in prompt.SYSTEM
