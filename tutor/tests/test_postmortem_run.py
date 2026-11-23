# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The analysis: code measures and keeps, the model names ideas and changes."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import pytest

from tutor import sources
from tutor.curriculum.context import Context
from tutor.postmortem import deck, evidence, lessons, prompt, run, show
from tutor.store import data_dir
from tutor.tests import _pm
from tutor.tests._cur import review

if TYPE_CHECKING:
    from pathlib import Path


class Draft:
    """The draft tier: scripted answers, prompts recorded."""

    def __init__(self, *replies: Any) -> None:
        self.replies = list(replies)
        self.prompts: list[str] = []

    def __call__(self, system: str, text: str, schema: dict[str, Any]) -> Any:
        assert system == prompt.SYSTEM
        assert schema == prompt.SCHEMA
        self.prompts.append(text)
        found = self.replies.pop(0)
        if isinstance(found, Exception):
            raise found
        return found


@pytest.fixture
def cur(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Context:
    monkeypatch.setattr(sources, "CACHE_DIR", tmp_path / "src-cache")
    ctx = Context(data_dir())
    _pm.unit_subject(ctx)
    return ctx


def _request(*solves: str) -> evidence.Request:
    found = evidence.parse_request(_pm.guard_row(solves=list(solves)))
    assert found is not None
    return found


def _solves(now: float) -> None:
    """p1: post one-shot; p2: post, 2 misses; p3: pre-theory one-shot."""
    late = int(now) + 3600
    _pm.history("p1", ("Accepted", late, "sum = prefix[r] - prefix[l]"))
    _pm.history(
        "p2",
        ("Wrong Answer", late, "loop"),
        ("Wrong Answer", late + 1, "loop2"),
        ("Accepted", late + 2, "fixed"),
    )
    _pm.history("p3", ("Accepted", 1000, "early"))


def test_the_analysis_merges_code_measures_with_the_models_reading(
    cur: Context,
) -> None:
    _solves(time.time())
    review(cur, _pm.LC, "a1", cur.clock() + 1, 1)
    draft = Draft(_pm.reply())
    cur.draft = draft
    got = run.analyse(cur, _request("p1", "p2", "p3"))
    assert got["one_shot"] == {"post": [1, 2], "pre": [1, 1]}
    assert got["kept_basis"] == "post"
    by_slug = {p["slug"]: p for p in got["problems"]}
    assert [p["slug"] for p in got["problems"]] == ["p3", "p1", "p2"]
    assert by_slug["p1"]["used"] == ["a0"]  # an unknown id is dropped
    assert (by_slug["p2"]["tries"], by_slug["p2"]["instead"]) == (2, "brute force")
    assert by_slug["p3"]["finding"] == ""  # the model named no p3
    cards = {c["id"]: c for c in got["cards"]}
    assert cards["a0"]["change"] == "kept"  # an edit of a kept card is refused
    assert cards["a0"]["used_by"] == ["p1"]
    assert cards["a0"]["new_front"] == ""
    assert (cards["a1"]["change"], cards["a1"]["new_front"]) == ("edit", "Better a1?")
    assert cards["a1"]["again"] == 1
    assert cards["a2"]["change"] == "suspend"
    assert cards["a3"]["change"] == "same"  # an edit with no text
    assert [c["front"] for c in got["new_cards"]] == [
        "When does a prefix sum need a 0 sentinel?"
    ]
    assert [k["card"] for k in got["lessons"]["keep"]] == ["a0"]
    assert [f["pattern"] for f in got["lessons"]["fix"]] == ["Teach the sentinel"]
    assert [f["module"] for f in got["future"]] == ["b"]
    assert got["seen"] == ["p1", "p2", "p3"]
    text = draft.prompts[0]
    assert "[a1] (a, taught, 1 reviews, 1 Again)" in text
    assert "## p2 (post-theory; 2 failed before Accepted" in text
    assert "Last failing code:\n```\nloop2" in text
    assert "- b: B." in text
    report = show.text(got)
    assert "one-shot post-theory 1/2 (50%); pre-theory 1/1 (100%)" in report
    assert "[kept] a0" in report
    assert "instead: brute force" in report


def test_with_no_post_theory_one_shot_any_one_shot_keeps(cur: Context) -> None:
    _pm.history("p3", ("Accepted", 1000, "early"))
    cur.draft = Draft(
        _pm.reply(
            problems=[
                {
                    "slug": "p3",
                    "used": ["a2"],
                    "skipped": [],
                    "instead": "",
                    "finding": "",
                }
            ],
            future="bad",
        )
    )
    got = run.analyse(cur, _request("p3", "p9"))
    assert got["kept_basis"] == "any"
    assert {c["id"]: c["change"] for c in got["cards"]}["a2"] == "kept"
    assert got["one_shot"] == {"post": [0, 0], "pre": [1, 1]}
    assert got["future"] == []
    assert "one-shot post-theory 0/0;" in show.text(got)


def test_a_model_failure_reaches_the_caller(cur: Context) -> None:
    cur.draft = Draft(OSError("down"))
    with pytest.raises(OSError, match="down"):
        run.analyse(cur, _request("p1"))


def test_a_sparse_answer_reads_as_no_change(cur: Context) -> None:
    cur.draft = Draft({"problems": "x", "cards": None, "lessons": None})
    got = run.analyse(cur, _request("p1"))
    assert {c["change"] for c in got["cards"]} == {"same"}
    assert got["new_cards"] == []
    assert got["lessons"] == {"fix": [], "keep": []}
    assert got["skills_md"] == ""


def test_the_deck_reads_paths_and_future_modules(cur: Context) -> None:
    folder = cur.subjects.dir(_pm.LC)
    (folder / "paths.json").write_text(
        '{"a0": {"rev": 1, "path": {"q": "'
        + "x" * 700
        + '"}}, "a1": {"rev": 9, "path": {}}}'
    )
    cards = deck.unit_cards(cur, _pm.LC, ("a",))
    assert cards[0].path.endswith("[...]")
    assert "Path:" in cards[0].line()
    assert cards[1].path == ""
    assert deck.future_modules(cur, "nothing", ("a",)) == []
    assert deck.module_text(cur, "nothing", ("a",)) == ""
    assert deck.future_modules(cur, _pm.LC, ("a",))[0]["taught"] == 0


def test_lessons_are_signed_and_feed_text(cur: Context) -> None:
    assert lessons.text(_pm.LC) == ""
    fix = [{"pattern": "Teach the sentinel", "why": "p2"}]
    keep = [{"card": "a0", "opening": "What?", "toy": "[1]", "words": 9, "why": "ok"}]
    assert lessons.record(_pm.LC, {"unit": "u", "rev": 1, "fix": fix, "keep": keep})
    text = lessons.text(_pm.LC)
    assert "- FIX (u): Teach the sentinel (p2)" in text
    assert "- KEEP (u): open like 'What?', toy example '[1]', about 9 words" in text
    for _ in range(100):
        lessons.record(_pm.LC, {"unit": "u", "rev": 2, "fix": fix * 2, "keep": []})
    assert len(lessons.text(_pm.LC)) == lessons.MAX_TEXT
    path = data_dir() / "postmortems" / _pm.LC / "lessons.json"
    path.write_text(path.read_text().replace("sentinel", "forged"))
    assert lessons.text(_pm.LC) == ""
    assert lessons.clean(None, set()) == {"fix": [], "keep": []}
    odd = lessons.clean({"keep": [{"card": "a0", "words": "9"}]}, {"a0"})
    assert odd["keep"][0]["words"] == 0
