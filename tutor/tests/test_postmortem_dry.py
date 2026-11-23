# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The dry run: started as a unit, polled with 75, writes only its result file."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest

from tutor import sources
from tutor.curriculum.context import Context
from tutor.curriculum.errors import MODEL_ERROR, RequestError
from tutor.postmortem import cli, dry, files
from tutor.store import data_dir
from tutor.tests import _pm

if TYPE_CHECKING:
    from pathlib import Path


class Runner:
    """``systemctl is-active`` answers ``active``; records every argv."""

    def __init__(self, active: int = 3, start: int = 0) -> None:
        self.calls: list[list[str]] = []
        self.active, self.start = active, start

    def __call__(self, argv: list[str]) -> int:
        self.calls.append(argv)
        return self.active if argv[0] == "systemctl" else self.start


@pytest.fixture
def cur(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Context:
    monkeypatch.setattr(sources, "CACHE_DIR", tmp_path / "src-cache")
    ctx = Context(data_dir())
    _pm.unit_subject(ctx)
    _pm.history("p1", ("Accepted", 1, "code"))
    return ctx


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file() and "postmortems" not in p.parts and p.suffix != ".lock"
    }


def test_auto_starts_the_unit_then_waits_then_prints(
    cur: Context, capsys: pytest.CaptureFixture[str]
) -> None:
    _pm.write_rows("preview", _pm.guard_row(files.PREVIEW_KIND, ["p1"]))
    runner = Runner()
    assert dry.auto(_pm.UNIT, runner) == dry.PENDING
    started = runner.calls[-1]
    assert started[:4] == [
        "systemd-run",
        "--user",
        "--collect",
        "--unit=tutor-postmortem-dry-prefix-sums",
    ]
    assert started[-3:] == [_pm.UNIT, "--dry-run", "run"]
    assert any(a.startswith("-ETUTOR_DATA=") for a in started)
    assert dry.auto(_pm.UNIT, Runner(active=0)) == dry.PENDING
    assert "is running" in capsys.readouterr().out
    before = _snapshot(cur.data_dir)
    cur.draft = lambda *_: _pm.reply()
    assert dry.work(cur, _pm.UNIT) == 0
    assert _snapshot(cur.data_dir) == before  # no card, event, state or report
    assert "post-mortem prefix-sums" in capsys.readouterr().out
    assert dry.auto(_pm.UNIT, Runner()) == 0
    assert "one-shot post-theory" in capsys.readouterr().out


def test_a_new_request_reruns_and_a_failure_is_reported(
    cur: Context, capsys: pytest.CaptureFixture[str]
) -> None:
    _pm.write_rows("preview", _pm.guard_row(files.PREVIEW_KIND, ["p1"]))

    def down(*_: Any) -> Any:
        raise RequestError(MODEL_ERROR, "model down")

    cur.draft = down
    assert dry.work(cur, _pm.UNIT) == 1
    assert dry.auto(_pm.UNIT, Runner()) == 1
    assert "failed: model down" in capsys.readouterr().out
    _pm.write_rows("preview", _pm.guard_row(files.PREVIEW_KIND, ["p1"], at=_pm.AT + 1))
    assert dry.auto(_pm.UNIT, Runner(start=1)) == 1
    assert "could not start" in capsys.readouterr().out


def test_no_signed_request_refuses(
    cur: Context, capsys: pytest.CaptureFixture[str]
) -> None:
    assert dry.auto(_pm.UNIT, Runner()) == 2
    assert dry.work(cur, _pm.UNIT) == 2
    forged = _pm.guard_row(files.PREVIEW_KIND, ["p1"])
    forged["detail"]["solves"] = ["p9"]
    _pm.write_rows("preview", forged)
    assert dry.auto(_pm.UNIT, Runner()) == 2
    assert "no signed dry-run request" in capsys.readouterr().out
    files.dry_path(_pm.UNIT).parent.mkdir(parents=True)
    files.dry_path(_pm.UNIT).write_text("[]")
    _pm.write_rows("preview", _pm.guard_row(files.PREVIEW_KIND, ["p1"]))
    assert dry.auto(_pm.UNIT, Runner()) == dry.PENDING  # a non-object result is none


def test_the_cli_routes_and_refuses(
    cur: Context, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    assert cli.main(["../x", "--dry-run"]) == 2
    assert cli.main([_pm.UNIT]) == 2
    seen: list[str] = []

    def auto(unit: str) -> int:
        seen.append(f"auto {unit}")
        return 75

    def work(_ctx: object, unit: str) -> int:
        seen.append(f"work {unit}")
        return 0

    monkeypatch.setattr(dry, "auto", auto)
    monkeypatch.setattr(dry, "work", work)
    assert cli.main([_pm.UNIT, "--dry-run"]) == 75
    assert cli.main([_pm.UNIT, "--dry-run", "run"], make=lambda _: cur) == 0
    assert seen == [f"auto {_pm.UNIT}", f"work {_pm.UNIT}"]
    failed = files.failed_path(_pm.UNIT, 1)
    failed.parent.mkdir(parents=True)
    failed.write_text(json.dumps({"error": "x"}))
    assert cli.main([_pm.UNIT, "--retry"]) == 0
    assert not failed.exists()
    assert "1 failed marker(s) cleared" in capsys.readouterr().out


def test_the_subprocess_runner_returns_the_exit_code() -> None:
    assert dry._subprocess(["true"]) == 0
    assert dry._subprocess(["false"]) == 1
