# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The redraft run state, the drainer, the report and the final audit."""

from __future__ import annotations

import fcntl
import json
import re
from typing import TYPE_CHECKING, Any

import pytest

from tutor.curriculum import cardgen
from tutor.curriculum.errors import BAD_REQUEST, CLAUDE_UNAVAILABLE, RequestError
from tutor.curriculum.ids import ulid
from tutor.curriculum.redraft import drain, report, run
from tutor.tests._cur import T0, card, review, subject
from tutor.tests._redraft import Fable, car, draft

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def _no_search(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cardgen, "sources", lambda *_: "no search in tests")


def _flag(n: int, cid: str, rev: int, reason: str, subj: str = "car") -> dict[str, Any]:
    eid = ulid(T0 + n, bytes([n] * 10))
    event = {"dev": "d1", "eid": eid, "k": "flag", "at": T0 + n, "s": subj}
    return {**event, "c": cid, "rev": rev, "reason": reason}


def test_without_a_run_there_is_nothing_to_read_or_drain(tmp_path: Path) -> None:
    ctx, _ = car(tmp_path)
    assert run.pending(ctx) == []
    assert drain.drain(ctx) == []
    with pytest.raises(RequestError, match="no redraft run in") as err:
        run.units(ctx)
    assert err.value.code == BAD_REQUEST
    with pytest.raises(RequestError, match="no snapshot of car"):
        run.before(ctx, "car")


def test_a_run_still_pending_is_never_replaced(tmp_path: Path) -> None:
    ctx, _ = car(tmp_path)
    run.start(ctx)
    with pytest.raises(RequestError, match="still pending"):
        run.start(ctx)
    assert [u.name for u in run.pending(ctx)] == ["car/a"]


def test_a_subject_without_an_approved_plan_is_left_alone(tmp_path: Path) -> None:
    ctx, _ = car(tmp_path)
    subject(ctx, "bike", plan_status="draft", found={"b1": card("a", 1)})
    assert [u.name for u in run.start(ctx)] == ["car/a"]
    assert not (run.root(ctx) / "before" / "bike").exists()


def test_history_counts_current_flags_and_hard_cards(tmp_path: Path) -> None:
    ctx, _ = car(tmp_path)
    ctx.log.append(
        [
            _flag(1, "old-1", 1, "too Hard to recall"),
            _flag(2, "old-1", 2, "another rev"),
            _flag(3, "old-1", 1, "other subject", subj="bike"),
            _flag(4, "nope", 1, "not a card"),
        ]
    )
    review(ctx, "car", "old-0", T0 + 5000, run.AGAIN)
    got = run.history(ctx, "car", ctx.subjects.cards("car"))
    assert got == {
        "flags": {"old-1": ["too Hard to recall"]},
        "hard": ["old-0", "old-1"],
        "taught": ["old-0"],
    }


def test_an_outage_leaves_the_unit_pending_and_costs_no_try(tmp_path: Path) -> None:
    ctx, _ = car(tmp_path)
    fable = Fable([draft("piston")])
    fable.fail = RequestError(CLAUDE_UNAVAILABLE, "claude is down")
    ctx.draft = fable
    run.start(ctx)
    (ended,) = drain.drain(ctx)
    assert (ended.state, ended.tries, ended.error) == (run.PENDING, 0, "claude is down")
    assert run.pending(ctx)[0].error == "claude is down"
    fable.fail = None
    (again,) = drain.drain(ctx)
    assert (again.state, again.tries, again.error) == (run.DONE, 1, "")


def test_a_second_drainer_on_the_same_data_dir_does_nothing(tmp_path: Path) -> None:
    ctx, _ = car(tmp_path)
    fable = Fable([draft("piston")])
    ctx.draft = fable
    run.start(ctx)
    with (run.root(ctx) / "drain.lock").open("w") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        assert drain.drain(ctx) == []
    assert fable.seen == []
    assert [u.state for u in run.units(ctx)] == [run.PENDING]


def test_the_default_report_path_is_stamped_with_the_start_time(tmp_path: Path) -> None:
    ctx, _ = car(tmp_path)
    run.start(ctx)
    path = report.write(ctx)
    started = json.loads((run.root(ctx) / "run.json").read_text())["started"]
    assert path == report.default_path(started)
    assert re.fullmatch(r"\d{8}-\d{6}", path.parent.name)
    assert path.parent.parent.parts[-4:] == (".local", "state", "tutor", "redraft")
    assert "# Redraft report" in path.read_text()


def test_a_report_without_a_run_writes_nothing(tmp_path: Path) -> None:
    ctx, _ = car(tmp_path)
    where = tmp_path / "r" / "report.md"
    with pytest.raises(RequestError, match="no redraft run"):
        report.write(ctx, where)
    assert not where.parent.exists()


def test_the_report_shows_a_flagged_card_after_and_without_a_successor(
    tmp_path: Path,
) -> None:
    ctx, _ = car(tmp_path)
    ctx.log.append(
        [_flag(1, "old-0", 1, "hard to recall"), _flag(2, "old-2", 1, "drop it")]
    )
    fable = Fable(
        [draft("piston", mnemonic="a piston is a pushy thumb"), draft("crank")],
        pairs=[("piston", "old-0"), ("crank", "old-1")],
    )
    ctx.draft = fable
    run.start(ctx)
    assert [u.state for u in drain.drain(ctx)] == [run.DONE]
    text = report.render(ctx)
    assert "- after: rev 2\n  - Q: What does the piston do?" in text
    assert "  - mnemonic: a piston is a pushy thumb" in text
    assert "- after: (no successor: the card is suspended)" in text
    assert "- `old-2`: What is thing 3 of a?" in text
