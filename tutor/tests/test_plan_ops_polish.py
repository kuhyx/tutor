# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Subject ids from Polish goals: letters kept, Polish filler stripped."""

from __future__ import annotations

from typing import TYPE_CHECKING
import unicodedata

import pytest

from tutor.curriculum import plan_ops
from tutor.tests._cur import make_ctx
from tutor.tests.test_planner import plan_reply

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("goal", "want"),
    [
        ("Chcę rozumieć pojęcia z maila", "pojęcia-z-maila"),
        ("chce rozumiec pojecia z maila", "pojecia-z-maila"),
        ("CHCĘ SIĘ NAUCZYĆ gry na gitarze", "gry-na-gitarze"),
        ("Chce sie nauczyc fizyki", "fizyki"),  # codespell:ignore sie
        ("Chcę nauczyć się fizyki", "fizyki"),
        ("Chcę wiedzieć o czarnych dziurach", "czarnych-dziurach"),
        ("Chcę zrozumieć ekonomię", "ekonomię"),
        ("chcę poznać Łódź", "łódź"),
        ("Chciałbym zrozumieć ekonomię", "ekonomię"),
        ("Chcesz poznać Łódź", "chcesz-poznać-łódź"),  # not a filler
        ("Chcę poznać", "chcę-poznać"),  # nothing left after it: keep the words
        ("Pojęcia z maila", "pojęcia-z-maila"),  # no filler at all
    ],
)
def test_subject_id_strips_polish_filler(goal: str, want: str) -> None:
    assert plan_ops.subject_id(goal, set()) == want


def test_subject_id_matches_the_filler_in_nfd_input() -> None:
    goal = unicodedata.normalize("NFD", "Chcę się nauczyć gry na łódce")
    assert goal != unicodedata.normalize("NFC", goal)
    assert plan_ops.subject_id(goal, set()) == "gry-na-łódce"


def test_subject_new_with_a_polish_goal_gets_a_polish_id(tmp_path: Path) -> None:
    ctx, fakes = make_ctx(tmp_path)
    fakes.replies = [plan_reply("a", "b", "c")]
    goal = "Chcę rozumieć pojęcia z maila"
    assert plan_ops.subject_new({"text": goal}, ctx) == {"subject": "pojęcia-z-maila"}
    assert ctx.subjects.need_meta("pojęcia-z-maila").goal == goal
    assert "pojęcia-z-maila" in ctx.subjects.subjects()
