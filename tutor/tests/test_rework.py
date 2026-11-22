# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``rework_open`` / ``rework_turn``: the lock's ``?`` adds cards to a module.

The cards land untaught in the guard's (subject, module), so module_state's
own reconcile writes the signed not-done row that sends the lock back to
THEORY; the handler never writes it.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest

from tutor import sources
from tutor.curriculum import card_ops
from tutor.curriculum.context import Context
from tutor.curriculum.errors import EDIT_REFUSED
from tutor.curriculum.errors import RequestError as CurriculumError
from tutor.relay import rework, rework_context
from tutor.relay.errors import RequestError
from tutor.store import data_dir
from tutor.tests import _lc_support as s
from tutor.tests._cur import card, module, subject, taught
from tutor.tests._phase import grant

if TYPE_CHECKING:
    from pathlib import Path

LC = "leetcode-easy-algorithms-in-typescript"
SLUG = "two-sum"
OPEN = {"subject": LC, "module": "a", "slug": SLUG}
CARD = {"front": "Which lookup finds a complement in O(1)?", "back": "A hash map."}


class Model:
    """Scripted ``ask_model`` answers; records every prompt."""

    def __init__(self) -> None:
        self.replies: list[dict[str, Any]] = []
        self.prompts: list[str] = []

    def __call__(self, system: str, prompt: str, schema: dict[str, Any]) -> Any:
        assert "rework" in system
        assert schema["properties"]["cards"]["maxItems"] == rework.MAX_CARDS
        self.prompts.append(prompt)
        return self.replies.pop(0)


@pytest.fixture
def cur(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Context:
    monkeypatch.setattr(sources, "CACHE_DIR", tmp_path / "src-cache")
    ctx = Context(data_dir())
    a0 = card("a", 0)
    subject(ctx, LC, modules=[module("a", status="ready", cards=1)], found={"a0": a0})
    grant((LC, "a"))
    taught(ctx, LC, "a0", ctx.clock())
    return ctx


@pytest.fixture
def model(monkeypatch: pytest.MonkeyPatch) -> Model:
    fake = Model()
    monkeypatch.setattr(rework, "ask_model", fake)
    return fake


def _flips(ctx: Context) -> list[tuple[str, str, bool]]:
    raw = json.loads((data_dir() / "module_state.json").read_text())
    return [
        (r["detail"]["subject"], r["detail"]["module"], r["detail"]["done"])
        for r in raw["entries"]
    ]


def _open(cur: Context, **body: Any) -> dict[str, Any]:
    return s.call("rework_open", {**OPEN, **body}, cur)


def _turn(cur: Context, rid: str, text: str = "Why a map?") -> dict[str, Any]:
    return s.call("rework_turn", {"rework_id": rid, "text": text}, cur)


def _history(tmp_path: Path, rows: object) -> None:
    folder = tmp_path / "guard" / "history"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{SLUG}.json").write_text(json.dumps(rows), encoding="utf-8")


def test_open_refuses_what_the_guard_cannot_mean(cur: Context) -> None:
    other = {"subject": "car", "module": "a", "slug": SLUG}
    with pytest.raises(RequestError, match="not a LeetCode subject"):
        s.call("rework_open", other, cur)
    with pytest.raises(RequestError, match="has no module 'zz'"):
        _open(cur, module="zz")
    missing = "javascript-and-pandas-for-leetcode-easy"
    with pytest.raises(RequestError, match="has no module"):
        _open(cur, subject=missing)
    with pytest.raises(RequestError, match="'slug' is missing or invalid"):
        _open(cur, slug="../x")
    with pytest.raises(RequestError, match="unknown rework"):
        _turn(cur, "0" * 12)


def test_open_names_the_session_and_its_history_without_the_model(
    cur: Context, model: Model, tmp_path: Path
) -> None:
    _history(tmp_path, {"submissions": [{"status": "Accepted", "timestamp": 1}]})
    got = _open(cur)
    assert got["rework_id"] == rework.rework_id(LC, "a", SLUG)
    assert got["module_title"] == "A"
    assert (got["thread"], got["cards"]) == ([], [])
    assert got["history"] == {"submissions": 1, "days": 0, "sessions": 0}
    assert model.prompts == []


def test_a_turn_adds_marked_cards_and_the_module_is_owed_again(
    cur: Context, model: Model
) -> None:
    assert _flips(cur) == [(LC, "a", True)]
    rid = _open(cur)["rework_id"]
    short = {"front": "Which operator cancels a pair?", "back": "XOR."}
    dup = {"front": " what is THING 0 of a? ", "back": "Again."}
    model.replies.append({"reply_md": "Two cards.", "cards": [CARD, short, dup]})
    got = _turn(cur, rid)
    assert got["reply_md"] == "Two cards."
    assert [c["front"] for c in got["cards"]] == [CARD["front"], short["front"]]
    assert (got["refused"], got["added"]) == ([], 2)
    stored = cur.subjects.cards(LC)
    for row in got["cards"]:
        rec = stored[row["id"]]
        assert rec.module == "a"
        assert rec.source.startswith(f"{rework.SOURCE_HOST}/{SLUG}/")
        assert rec.tutor["source"] == f"rework:{SLUG}"
        assert sources.check_excerpt(row["id"], rec.source, rec.excerpt) is None
    assert _flips(cur) == [(LC, "a", True), (LC, "a", False)]
    again = _open(cur)
    assert again["thread"] == [
        {"mine": True, "md": "Why a map?"},
        {"mine": False, "md": "Two cards."},
    ]
    assert [c["id"] for c in again["cards"]] == [c["id"] for c in got["cards"]]
    model.replies.append({"reply_md": "More?", "cards": []})
    _turn(cur, rid, "Still lost.")
    assert "kuhy: Why a map?" in model.prompts[1]
    assert CARD["front"] in model.prompts[1]


def test_a_turn_caps_the_cards_and_reports_refusals(
    cur: Context, model: Model, monkeypatch: pytest.MonkeyPatch
) -> None:
    rid = _open(cur)["rework_id"]
    many = [{"front": f"Which step {n} comes next?", "back": "x"} for n in range(7)]
    model.replies.append({"reply_md": "", "cards": [{"front": " "}, *many]})
    seen: list[str] = []

    def refuse(ctx: Context, subj: str, draft: card_ops.Draft) -> Any:
        del ctx, subj
        seen.append(draft.front)
        raise CurriculumError(EDIT_REFUSED, "too short")

    monkeypatch.setattr(card_ops, "add", refuse)
    got = _turn(cur, rid)
    assert len(seen) == rework.MAX_CARDS - 1
    assert got["refused"][0] == {"front": many[0]["front"], "reason": "too short"}
    assert (got["cards"], got["added"]) == ([], 0)


def test_a_dropped_subject_refuses_the_turn(cur: Context, model: Model) -> None:
    rid = _open(cur)["rework_id"]
    plan = cur.subjects.plan(LC)
    assert plan is not None
    plan.modules[0].id = "b"
    from tutor.curriculum.subject_store import Change

    cur.subjects.commit(LC, cur.subjects.need_meta(LC), Change(plan=plan))
    with pytest.raises(RequestError, match="has no module 'a'"):
        _turn(cur, rid)
    assert model.prompts == []


def test_the_prompt_carries_the_history_bounded(
    cur: Context, model: Model, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(rework_context, "MAX_SUBMISSIONS", 2)
    monkeypatch.setattr(rework_context, "MAX_CODE", 10)
    rows = [
        {"status": "Wrong Answer", "lang": "python3", "timestamp": 100, "code": "a"},
        {"status": "Accepted", "lang": "python3", "timestamp": 300, "code": "x" * 50},
        {"status": "Time Limit", "lang": "python3", "timestamp": 200},
    ]
    _history(tmp_path, {"submissions": rows})
    rid = _open(cur)["rework_id"]
    model.replies.append({"reply_md": "ok", "cards": []})
    _turn(cur, rid)
    prompt = model.prompts[0]
    assert "Accepted" in prompt
    assert "Time Limit" in prompt
    assert "Wrong Answer" not in prompt
    assert "x" * 10 + " [...]" in prompt
    assert "x" * 11 not in prompt
    assert "Module: A" in prompt


@pytest.mark.parametrize(
    ("kind", "body", "field"),
    [
        ("rework_open", {**OPEN, "subject": "Bad Id"}, "subject"),
        ("rework_turn", {"rework_id": "XYZ", "text": "hi"}, "rework_id"),
        ("rework_turn", {"rework_id": "0" * 12, "text": "  "}, "text"),
    ],
)
def test_bad_fields_are_bad_requests(
    kind: str, body: dict[str, Any], field: str
) -> None:
    with pytest.raises(RequestError, match=f"'{field}' is missing or invalid"):
        s.validate(kind, body)
