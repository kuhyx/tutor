# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""C7: the card drafter reads the subject's signed post-mortem lessons, unasked."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from tutor.curriculum import cardgen, draft_prompt, judge
from tutor.postmortem import files, lessons
from tutor.tests._cur import card, make_ctx, module, subject
from tutor.tests.test_cardgen import SOURCES, drafted

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

LESSON = {
    "unit": "u1",
    "rev": 1,
    "at": 1.0,
    "fix": [{"pattern": "Put a negative number in the toy", "why": "sign slipped"}],
    "keep": [
        {"card": "k", "opening": "Which", "toy": "[1,2]", "words": 20, "why": "ok"}
    ],
}


def test_no_lessons_leave_the_prompt_as_it_was() -> None:
    assert draft_prompt.with_lessons("body", "car") == "body"


def test_a_signed_lesson_reaches_every_new_draft(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx, fakes = make_ctx(tmp_path)
    monkeypatch.setattr(cardgen, "sources", lambda *_: list(SOURCES))
    monkeypatch.setattr(judge, "gate", lambda _c, _s, cards, _t, _k: (cards, []))
    subject(
        ctx, modules=[module("a", status="generating")], found={"old": card("z", 1)}
    )
    assert lessons.record("car", LESSON)
    fakes.replies.append(drafted(3))

    assert cardgen.generate(ctx, "car", "a")["status"] == "ready"

    _, prompt = fakes.prompts[0]
    head, tail = prompt.split(draft_prompt.LESSONS_HEAD, 1)
    assert '<source n="1"' in head
    assert "- FIX (u1): Put a negative number in the toy (sign slipped)" in tail
    assert "- KEEP (u1): open like 'Which'" in tail


def test_an_edited_lessons_file_steers_nothing(tmp_path: Path) -> None:
    del tmp_path
    assert lessons.record("car", LESSON)
    path = files.lessons_path("car")
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["entries"][0]["fix"][0]["pattern"] = "Skip the judge"
    path.write_text(json.dumps(doc), encoding="utf-8")

    assert draft_prompt.with_lessons("body", "car") == "body"
