# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Answer choices: repaired from the model, aligned with the questions, shown."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest

from tutor import choices, media, resume
from tutor.models import TutorTurn
from tutor.tests._fakes import turn
from tutor.tests._media_support import DRAFT, live, picture, run
from tutor.tests.test_models import raw_turn

if TYPE_CHECKING:
    from pathlib import Path

THREE = ("24 V DC", "230 V AC", "5 V DC")


@pytest.fixture(autouse=True)
def _no_shuffle(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the model's order so the tests can compare lists."""
    monkeypatch.setattr(choices, "mixed", lambda choice: choice)


def test_entry_keeps_three_distinct_short_strings_stripped() -> None:
    assert choices.entry([" 24 V DC ", "230 V AC", "5 V DC"]) == THREE
    assert choices.entry(THREE) == THREE  # a logged tuple reads the same


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "24 V DC",
        ["a", "b"],
        ["a", "b", "c", "d"],
        ["a", "b", 3],
        ["a", " ", "c"],
        ["Coil", "coil", "relay"],
        ["a", "b", " ".join(["word"] * (choices.MAX_WORDS + 1))],
    ],
)
def test_entry_drops_anything_but_three_usable_answers(raw: object) -> None:
    assert choices.entry(raw) == ()


def test_mixed_keeps_the_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.undo()  # the real shuffle this time
    for _ in range(5):
        assert sorted(choices.mixed(THREE)) == sorted(THREE)


def test_pair_drops_a_blank_question_with_its_choices() -> None:
    questions, offered = choices.pair(["A?", " ", "C?"], [[], list(THREE), ["x"]])
    assert questions == ("A?", "C?")
    assert offered == ((), ())  # B's choices went with B; C's were broken


@pytest.mark.parametrize("raw", [None, "x", {"0": THREE}])
def test_pair_without_a_choices_list_offers_none(raw: object) -> None:
    assert choices.pair(["A?", "B?"], raw) == (("A?", "B?"), ((), ()))


def test_aligned_pads_and_cuts_to_the_questions() -> None:
    assert choices.aligned(["A?", "B?"], [list(THREE)]) == [list(THREE), []]
    assert choices.aligned(["A?"], [[], list(THREE)]) == [[]]
    assert choices.aligned([], None) == []


def test_boxes_drop_the_check_and_its_choices_together() -> None:
    got = choices.boxes(
        ["Why 24 V?", "Which?"], [list(THREE), list(THREE)], "Why 24 V?"
    )
    assert got == (["Which?"], [list(THREE)])


def test_from_json_repairs_choices_and_tolerates_their_absence() -> None:
    parsed = TutorTurn.from_json(
        raw_turn(choices=[list(THREE), ["two", "only"], ["x", "y", "z"]])
    )
    assert parsed.questions == ("What is a coil?", "4")
    # The blank question took the broken entry with it; "4" keeps its own.
    assert parsed.choices == (THREE, ("x", "y", "z"))
    old = {k: v for k, v in raw_turn().items() if k != "choices"}
    assert TutorTurn.from_json(old).choices == ((), ())


def test_page_message_lines_choices_up_with_the_boxes() -> None:
    check = {"question": "Why 24 V?", "concept": "coil"}
    message = media.page_message(
        turn(
            "Look.", questions=("Why 24 V?", "Which?"), choices=((), THREE), check=check
        )
    )
    assert message["questions"] == ["Which?"]
    assert message["choices"] == [list(THREE)]
    assert media.page_message(turn("Q.", questions=("A?",)))["choices"] == [[]]


def _checked(commons: dict[str, Any], **fields: Any) -> TutorTurn:
    commons["relay"] = picture("relay", "Relay")
    return turn("A relay.", images=(("1",),), **fields)


def test_reworded_questions_take_the_check_replies_choices(
    tmp_path: Path, commons: dict[str, Any]
) -> None:
    other = ("a", "b", "c")
    reply = _checked(commons, questions=("This one?",), choices=(other,))
    draft = turn(DRAFT, images=(("relay",),), questions=("What?",), choices=(THREE,))
    message = run(live(tmp_path, reply), draft)
    assert (message["questions"], message["choices"]) == (["This one?"], [list(other)])


def test_reworded_questions_keep_the_drafts_choices_if_dropped(
    tmp_path: Path, commons: dict[str, Any]
) -> None:
    draft = turn(DRAFT, images=(("relay",),), questions=("What?",), choices=(THREE,))
    reply = _checked(commons, questions=("This one?",))
    assert run(live(tmp_path, reply), draft)["choices"] == [list(THREE)]
    # A different number of questions: the draft's choices no longer fit.
    reply = _checked(commons, questions=("This one?", "And?"))
    assert run(live(tmp_path, reply), draft)["choices"] == [[], []]


def test_old_transcripts_replay_with_no_choices(tmp_path: Path) -> None:
    t0 = 1_800_000_000.0
    old_turn = {"message": "Hi", "questions": ["A?", "B?"], "low_effort": False}
    new_turn = {**old_turn, "choices": [list(THREE)]}
    events = [
        {"type": "start", "card": "c", "t": t0},
        {"type": "tutor", "turn": old_turn, "t": t0 + 1},
        {"type": "tutor", "turn": new_turn, "t": t0 + 2},
        {"type": "tutor", "turn": old_turn, "t": t0 + 3, "ui": {"questions": ["Q?"]}},
    ]
    path = tmp_path / "20261015-090000-abcd.jsonl"
    path.write_text("".join(json.dumps(e) + "\n" for e in events))
    replayed = resume.replay(path)
    assert replayed is not None
    got = [m["choices"] for m in replayed.conversation.messages]
    assert got == [[[], []], [list(THREE), []], [[]]]
