# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``python -m tutor redraft``: start, status, drain, report."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tutor import store
from tutor.curriculum import cardgen
from tutor.curriculum.context import Context
from tutor.curriculum.errors import CLAUDE_UNAVAILABLE, RequestError
from tutor.curriculum.redraft import cli, run
from tutor.tests._redraft import Fable, car, draft

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.fixture(autouse=True)
def _no_search(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cardgen, "sources", lambda *_: "no search in tests")


def _never(_seconds: float) -> None:
    pytest.fail("nothing should have waited")


def _maker(ctx: Context) -> Callable[[Path], Context]:
    return lambda _path: ctx


def test_status_without_a_run_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ctx, _ = car(tmp_path)
    assert cli.main(["status"], _maker(ctx), _never) == 2
    assert "refused: no redraft run in" in capsys.readouterr().out


def test_start_queues_the_units_and_status_says_pending(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ctx, _ = car(tmp_path)
    assert cli.main(["start"], _maker(ctx), _never) == 0
    assert f"queued 1 units in {run.root(ctx)}" in capsys.readouterr().out
    assert cli.main(["status"], _maker(ctx), _never) == cli.PENDING_EXIT
    assert capsys.readouterr().out == "pending  car/a\n"


@pytest.mark.parametrize(("only", "count"), [("car/zz", 0), ("car/a", 1)])
def test_only_queues_just_the_named_units(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], only: str, count: int
) -> None:
    ctx, _ = car(tmp_path)
    assert cli.main(["start", "--only", only], _maker(ctx), _never) == 0
    assert f"queued {count} units" in capsys.readouterr().out
    assert len(run.units(ctx)) == count


def test_replies_are_copied_into_the_run(tmp_path: Path) -> None:
    ctx, _ = car(tmp_path / "data")
    replies = tmp_path / "dry"
    replies.mkdir()
    (replies / "abc.json").write_text('{"cards": []}')
    assert cli.main(["start", "--replies", str(replies)], _maker(ctx), _never) == 0
    assert (run.root(ctx) / "replies" / "abc.json").read_text() == '{"cards": []}'


def test_drain_builds_every_unit_and_status_is_done(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ctx, _ = car(tmp_path)
    ctx.draft = Fable([draft("piston")], pairs=[("piston", "old-0")])
    cli.main(["start"], _maker(ctx), _never)
    capsys.readouterr()
    assert cli.main(["drain", "--workers", "1"], _maker(ctx), _never) == 0
    assert capsys.readouterr().out == "done     car/a\n"
    assert cli.main(["status"], _maker(ctx), _never) == 0
    assert ctx.subjects.cards("car")["old-0"].rev == 2


def test_drain_waits_out_an_outage_then_finishes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ctx, _ = car(tmp_path)
    fable = Fable([draft("piston")], pairs=[("piston", "old-0")])
    fable.fail = RequestError(CLAUDE_UNAVAILABLE, "claude is down")
    ctx.draft = fable
    cli.main(["start"], _maker(ctx), _never)
    napped: list[float] = []

    def nap(seconds: float) -> None:
        napped.append(seconds)
        fable.fail = None  # the outage is over

    assert cli.main(["drain"], _maker(ctx), nap) == 0
    assert napped == [cli.RETRY_S]
    (unit,) = run.units(ctx)
    assert (unit.state, unit.tries) == (run.DONE, 1)
    assert capsys.readouterr().out.endswith("done     car/a\n")


def test_a_unit_that_keeps_failing_ends_failed_with_exit_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ctx, _ = car(tmp_path)
    ctx.draft = Fable([draft("piston", source=9)])
    cli.main(["start"], _maker(ctx), _never)
    napped: list[float] = []
    assert cli.main(["drain"], _maker(ctx), napped.append) == 1
    assert napped == [cli.RETRY_S] * (run.MAX_TRIES - 1)
    out = capsys.readouterr().out
    assert "failed   car/a (car/a: no card passed" in out
    live = [c for c in ctx.subjects.cards("car").values() if not c.suspended]
    assert len(live) == 3  # the old cards stay


def test_drain_refuses_the_live_data_dir(
    capsys: pytest.CaptureFixture[str],
) -> None:
    live = Path.home() / ".local/share/tutor"
    assert cli.main(["drain", "--data", str(live)], Context, _never) == 2
    assert "refused: only the running server drains" in capsys.readouterr().out
    assert not (live / "redraft").exists()


def test_report_writes_the_file_and_prints_its_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ctx, _ = car(tmp_path / "data")
    cli.main(["start"], _maker(ctx), _never)
    capsys.readouterr()
    where = tmp_path / "out" / "report.md"
    assert cli.main(["report", "--out", str(where)], _maker(ctx), _never) == 0
    assert capsys.readouterr().out == f"{where}\n"
    assert "0 of 1 modules redrafted; 1 not done." in where.read_text()


def test_the_data_dir_defaults_to_the_tutor_one(tmp_path: Path) -> None:
    ctx, _ = car(tmp_path)
    asked: list[Path] = []

    def make(path: Path) -> Context:
        asked.append(path)
        return ctx

    cli.main(["status"], make, _never)
    cli.main(["status", "--data", str(tmp_path / "other")], make, _never)
    assert asked == [store.data_dir(), tmp_path / "other"]


def test_the_default_context_is_a_real_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["status", "--data", str(tmp_path / "empty")]) == 2
    assert "refused: no redraft run" in capsys.readouterr().out
