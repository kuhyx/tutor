# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""C4: ``review_due.json``, the signed due times of a module's review queue.

leetcode-guard reads it to count a module's due reviews at any time T
(``DOCS-contract-review-due.md``). Every path that moves a card's due time or
its queue membership rewrites the module's row: a taught event, a review, a
flag, a card commit (suspend, edit), an archive, and the startup backfill.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from tutor.curriculum import module_state, review_due
from tutor.curriculum.eventlog import worker_event
from tutor.curriculum.fold import fold
from tutor.curriculum.records import Plan
from tutor.curriculum.subject_store import Change
from tutor.engine import Engine
from tutor.store import Store
from tutor.tests._cur import T0, D, card, make_ctx, module, subject
from tutor.tests._due import (
    JS,
    LC,
    PHONE,
    SQL,
    due_of,
    make_lc,
    mirror,
    review,
    row_of,
    rows_of,
    teach,
)
from tutor.tests.conftest import KEY

if TYPE_CHECKING:
    from pathlib import Path


def test_a_module_lists_the_due_times_of_its_taught_cards(tmp_path: Path) -> None:
    ctx = make_lc(tmp_path, a0=card("a", 0), a1=card("a", 1), a2=card("a", 2))
    teach(ctx, "a0", T0 - 30 * D)
    teach(ctx, "a1", T0 - 20 * D)
    teach(ctx, "a2", T0)
    folded = fold(ctx.log.read())
    states = [folded.card(LC, c).fsrs_state() for c in ("a0", "a1", "a2")]
    want = sorted(s["due"] for s in states if s is not None)
    detail = row_of(tmp_path, LC, "a")["detail"]
    assert detail["due_ms"] == want
    assert detail["subject"] == LC
    assert detail["module"] == "a"
    assert isinstance(detail["at"], float)
    rows = rows_of(tmp_path)
    assert sorted(r["detail"]["module"] for r in rows) == [
        "a",
        "b",
    ]  # b: explicit empty
    assert due_of(tmp_path, "b") == []
    # The reader helper: 2 due now, all 3 in eight days (the third is days away).
    path = tmp_path / "review_due.json"
    assert review_due.count_due(path, KEY, LC, "a", T0) == 2
    assert review_due.count_due(path, KEY, LC, "a", T0 + 8 * D) == 3
    assert review_due.count_due(path, KEY, LC, "b", T0 + 8 * D) == 0


def test_the_row_has_the_documented_shape(tmp_path: Path) -> None:
    ctx = make_lc(tmp_path, a0=card("a", 0))
    teach(ctx, "a0")
    row = row_of(tmp_path, LC, "a")
    assert set(row) == {"kind", "entry_id", "day", "detail", "hmac"}
    assert row["kind"] == "review_due"
    assert row["entry_id"] == f"due:{LC}:a:2"  # :1 was the empty row at the commit
    assert row["day"] == "2027-01-15"
    assert set(row["detail"]) == {"subject", "module", "due_ms", "at"}
    assert all(type(t) is int for t in row["detail"]["due_ms"])


def test_a_review_moves_the_due_time_and_rewrites_the_row(tmp_path: Path) -> None:
    ctx = make_lc(tmp_path, a0=card("a", 0))
    teach(ctx, "a0", T0 - 30 * D)
    before = due_of(tmp_path)
    assert before[0] < T0
    assert row_of(tmp_path, LC, "a")["entry_id"] == f"due:{LC}:a:2"
    review(ctx, "a0", T0)
    after = due_of(tmp_path)
    assert after[0] > T0 + D  # a Good review pushed it out of the queue
    assert row_of(tmp_path, LC, "a")["entry_id"] == f"due:{LC}:a:3"
    assert len([r for r in rows_of(tmp_path) if r["detail"]["module"] == "a"]) == 1
    assert review_due.count_due(tmp_path / "review_due.json", KEY, LC, "a", T0) == 0


def test_an_event_that_moves_nothing_writes_nothing(tmp_path: Path) -> None:
    ctx = make_lc(tmp_path, a0=card("a", 0), a1=card("a", 1))
    teach(ctx, "a0")
    text = (tmp_path / "review_due.json").read_text()
    teach(ctx, "a0")  # same card, same moment, a new eid: the fold is unchanged
    again = (tmp_path / "review_due.json").read_text()
    assert again == text
    ctx.log.append(
        [worker_event("untaught", (LC, "a1"), dev=ctx.device, at=T0 + 1)]
    )  # an untaught card was never in the queue
    assert (tmp_path / "review_due.json").read_text() == text


def test_a_flagged_card_leaves_the_list_until_it_is_edited(tmp_path: Path) -> None:
    ctx = make_lc(tmp_path, a0=card("a", 0), a1=card("a", 1))
    teach(ctx, "a0", T0 - 30 * D)
    teach(ctx, "a1", T0 - 20 * D)
    assert len(due_of(tmp_path)) == 2
    flag = {"k": "flag", "s": LC, "c": "a0", "at": T0, "rev": 1, "reason": "wrong"}
    mirror(ctx, flag, "01HZZZZZZZZZZZZZZZZZZZZZZZ")
    assert len(due_of(tmp_path)) == 1
    cards = ctx.subjects.cards(LC)
    cards["a0"].rev = 2  # an edit bumps the rev, which clears the flag
    ctx.subjects.commit(LC, ctx.subjects.need_meta(LC), Change(cards=cards))
    assert len(due_of(tmp_path)) == 2


def test_a_suspended_card_leaves_the_list(tmp_path: Path) -> None:
    ctx = make_lc(tmp_path, a0=card("a", 0), a1=card("a", 1))
    teach(ctx, "a0")
    teach(ctx, "a1")
    assert len(due_of(tmp_path)) == 2
    cards = ctx.subjects.cards(LC)
    cards["a1"].suspended = True
    ctx.subjects.commit(LC, ctx.subjects.need_meta(LC), Change(cards=cards))
    assert len(due_of(tmp_path)) == 1
    cards["a1"].suspended = False
    ctx.subjects.commit(LC, ctx.subjects.need_meta(LC), Change(cards=cards))
    assert len(due_of(tmp_path)) == 2


def test_an_untaught_module_gets_an_explicit_empty_row(tmp_path: Path) -> None:
    ctx = make_lc(tmp_path, a0=card("a", 0))
    teach(ctx, "a0")
    assert due_of(tmp_path, "b") == []  # b has no card at all
    ctx.log.append([worker_event("untaught", (LC, "a0"), dev=ctx.device, at=T0 + 9)])
    assert due_of(tmp_path) == []  # a has a card, none taught: still a row


def test_a_new_module_in_the_plan_gets_its_row(tmp_path: Path) -> None:
    ctx = make_lc(tmp_path, a0=card("a", 0))
    teach(ctx, "a0")
    plan = ctx.subjects.plan(LC)
    assert plan is not None
    mods = [*plan.modules, module("c", status="ready")]
    ctx.subjects.commit(
        LC, ctx.subjects.need_meta(LC), Change(plan=Plan(2, "approved", "n", mods))
    )
    assert due_of(tmp_path, "c") == []


def test_an_archived_subject_has_nothing_due_like_the_queue(tmp_path: Path) -> None:
    ctx = make_lc(tmp_path, a0=card("a", 0))
    teach(ctx, "a0", T0 - 30 * D)
    assert len(due_of(tmp_path)) == 1
    archive = {"k": "subject_archive", "s": LC, "at": T0 + 1}
    ctx.log.append([{**archive, "dev": PHONE, "eid": "01HZZZZZZZZZZZZZZZZZZZZZZA"}])
    assert due_of(tmp_path) == []
    unarchive = {"k": "subject_unarchive", "s": LC, "at": T0 + 2}
    ctx.log.append([{**unarchive, "dev": PHONE, "eid": "01HZZZZZZZZZZZZZZZZZZZZZZB"}])
    assert len(due_of(tmp_path)) == 1


def test_other_subjects_write_no_rows(tmp_path: Path) -> None:
    ctx, _ = make_ctx(tmp_path)
    subject(
        ctx, "car", modules=[module("a", status="ready")], found={"c": card("a", 0)}
    )
    teach(ctx, "c", subj="car")
    assert not (tmp_path / "review_due.json").exists()


def test_startup_backfills_every_module_once(tmp_path: Path) -> None:
    ctx, _ = make_ctx(tmp_path)
    subject(ctx, LC, modules=[module("a", status="ready")], found={"a0": card("a", 0)})
    subject(ctx, JS, modules=[module("js", status="ready")])
    subject(ctx, SQL, modules=[module("joins", status="ready")])
    subject(ctx, "car", modules=[module("x", status="ready")])
    # An event the hook never saw: written straight to the file.
    event = worker_event("taught", (LC, "a0"), dev="dev-pc", at=T0 - 30 * D)
    (tmp_path / "log.jsonl").write_text(json.dumps(event) + "\n")
    engine = Engine(store=Store(tmp_path))
    engine.record_module_states()
    refs = sorted(
        (r["detail"]["subject"], r["detail"]["module"]) for r in rows_of(tmp_path)
    )
    assert refs == sorted([(LC, "a"), (JS, "js"), (SQL, "joins")])
    assert len(due_of(tmp_path)) == 1
    text = (tmp_path / "review_due.json").read_text()
    engine.record_module_states()  # a second start: the truth is on file already
    assert (tmp_path / "review_due.json").read_text() == text


def test_the_subjects_are_the_ones_of_c2() -> None:
    assert frozenset({LC, JS, SQL}) == module_state.SUBJECTS


def test_a_commit_of_neither_cards_nor_plan_writes_nothing(tmp_path: Path) -> None:
    ctx = make_lc(tmp_path, a0=card("a", 0))
    text = (tmp_path / "review_due.json").read_text()
    ctx.subjects.commit(LC, ctx.subjects.need_meta(LC), Change(concepts=[]))
    ctx.subjects.commit(LC, ctx.subjects.need_meta(LC))
    assert (tmp_path / "review_due.json").read_text() == text
