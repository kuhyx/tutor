# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The daily new-card cap: 25 by default, set in Settings, lifted for a day."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from tutor.credit import local_day
from tutor.curriculum import cap, rules
from tutor.curriculum.errors import RequestError
from tutor.curriculum.ids import ulid
from tutor.curriculum.stats import stats
from tutor.tests._cur import T0, D, card, make_ctx, module, subject, taught

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.curriculum.context import Context

_N = iter(range(1, 10_000))


def _set_cap(ctx: Context, n: object, at: int, dev: str = "phone") -> None:
    """A Settings ``new_cap`` event (``n`` unchecked: parse decides)."""
    ctx.log.append(
        [
            {"dev": dev, "eid": ulid(at, bytes([next(_N) % 256] * 10)), "k": "new_cap"}
            | {"n": n, "at": at}
        ]
    )


def _flag(ctx: Context, cid: str, at: int) -> None:
    ctx.log.append(
        [
            {
                "dev": "phone",
                "eid": ulid(at, bytes([200] * 10)),
                "k": "flag",
                "s": "hosting",
                "c": cid,
                "at": at,
                "rev": 1,
            }
        ]
    )


def _hosting(tmp_path: Path, taught_today: int = 25) -> tuple[Context, rules.View]:
    """``vhost-apache`` with 30 cards: 3 taught 10 days ago, ``taught_today`` new.

    Of the old three, c1 is suspended and c2 flagged: only c0 counts as due.
    """
    ctx, _ = make_ctx(tmp_path)
    found = {f"c{i:02d}": card("a", i) for i in range(30)}
    found["c01"].suspended = True
    mods = [module("a", status="ready")]
    mods[0].title = "vhost-apache"
    plan = subject(ctx, "hosting", modules=mods, found=found)
    for i in range(3):
        taught(ctx, "hosting", f"c{i:02d}", T0 - 10 * D + i, i)
    _flag(ctx, "c02", T0 - 9 * D)
    for i in range(3, 3 + taught_today):
        taught(ctx, "hosting", f"c{i:02d}", T0 + i, i)
    return ctx, rules.View("hosting", plan, found, title="Hosting WWW")


def _refused(view: rules.View, ctx: Context, now: int, cid: str | None = None) -> Any:
    with pytest.raises(RequestError) as err:
        rules.pick(view, ctx.fold(), cid, now)
    return err.value


def test_the_default_cap_is_25() -> None:
    assert cap.NEW_CAP == 25
    assert rules.NEW_CAP == 25


def test_the_cap_error_carries_the_one_tap_fix(tmp_path: Path) -> None:
    ctx, view = _hosting(tmp_path)
    err = _refused(view, ctx, T0 + 100)
    assert err.code == "daily_new_cap"
    assert err.extra == {
        "subject_title": "Hosting WWW",
        "new_today": 25,
        "new_cap": 25,
        "module": "a",
        "module_title": "vhost-apache",
        "due_in_subject": 1,
        "next": "lift_cap",
    }
    assert err.message == (
        "You learned 25 new cards today (the daily limit). “vhost-apache” is open."
    )
    assert err.result(5)["next"] == "lift_cap"
    explicit = _refused(view, ctx, T0 + 100, "c29")  # an explicit new card too
    assert explicit.code == "daily_new_cap"
    assert explicit.extra["module_title"] == "vhost-apache"


def test_a_lowered_cap_says_its_number(tmp_path: Path) -> None:
    ctx, view = _hosting(tmp_path)
    _set_cap(ctx, 5, T0 - D)
    err = _refused(view, ctx, T0 + 100)
    assert err.extra["new_cap"] == 5
    assert err.message == (
        "You learned 25 new cards today (the daily limit is 5). “vhost-apache” is open."
    )


def test_lift_then_start_works_and_a_second_lift_writes_nothing(
    tmp_path: Path,
) -> None:
    ctx, view = _hosting(tmp_path)
    assert not cap.lifted_today(ctx.fold(), T0 + 100)
    assert cap.lift(ctx) is True
    lifts = [e for e in ctx.log.read() if e["k"] == "cap_lift"]
    assert len(lifts) == 1
    assert lifts[0]["day"] == local_day(T0 / 1000)[0]
    assert lifts[0]["dev"] == ctx.device
    assert lifts[0]["at"] == T0
    assert cap.lifted_today(ctx.fold(), T0 + 100)
    assert rules.pick(view, ctx.fold(), None, T0 + 100) == "c28"
    assert cap.lift(ctx) is False  # idempotent: the day is lifted already
    assert [e["k"] for e in ctx.log.read()].count("cap_lift") == 1
    today = stats(ctx, {})["today"]
    assert today["new_cap_lifted"] is True
    assert today["new"] == 25  # the count stays honest


def test_a_lift_does_not_carry_over_to_the_next_day(tmp_path: Path) -> None:
    ctx, fakes = make_ctx(tmp_path)
    found = {f"c{i}": card("a", i) for i in range(6)}
    plan = subject(ctx, "hosting", modules=[module("a", status="ready")], found=found)
    view = rules.View("hosting", plan, found, title="Hosting WWW")
    _set_cap(ctx, 2, T0 - D)
    assert cap.lift(ctx)  # lifted on T0's day
    taught(ctx, "hosting", "c0", T0 + D, 0)
    taught(ctx, "hosting", "c1", T0 + D + 1, 1)
    fakes.now[0] = T0 + D
    assert not cap.lifted_today(ctx.fold(), T0 + D)
    assert stats(ctx, {})["today"]["new_cap_lifted"] is False
    err = _refused(view, ctx, T0 + D + 5)
    assert (err.code, err.extra["new_cap"], err.extra["new_today"]) == (
        "daily_new_cap",
        2,
        2,
    )
    assert cap.lift(ctx)  # a new day, a new lift
    assert rules.pick(view, ctx.fold(), None, T0 + D + 5) == "c2"


def test_effective_cap_default_set_latest_and_out_of_range(tmp_path: Path) -> None:
    ctx, _ = make_ctx(tmp_path)
    assert cap.effective_cap(ctx.fold()) == 25
    assert stats(ctx, {})["today"]["new_cap"] == 25
    _set_cap(ctx, 40, T0 - 2 * D, dev="desk")
    assert cap.effective_cap(ctx.fold()) == 40
    _set_cap(ctx, 7, T0 - 3 * D)  # older: the later 40 still wins
    assert cap.effective_cap(ctx.fold()) == 40
    _set_cap(ctx, 12, T0 - D)
    assert cap.effective_cap(ctx.fold()) == 12
    assert stats(ctx, {})["today"]["new_cap"] == 12
    for bad in (0, 201, -3, True, "30", 2.5, None):
        _set_cap(ctx, bad, T0)  # newest, but ignored
    assert cap.effective_cap(ctx.fold()) == 12
    _set_cap(ctx, 200, T0 + 1)
    _set_cap(ctx, 1, T0 + 2)
    assert cap.effective_cap(ctx.fold()) == 1


def test_lifted_days_come_from_any_device(tmp_path: Path) -> None:
    ctx, _ = make_ctx(tmp_path)
    day = local_day(T0 / 1000)[0]
    ctx.log.append(
        [
            {
                "dev": "phone",
                "eid": ulid(T0, b"\5" * 10),
                "k": "cap_lift",
                "day": day,
                "at": T0,
            }
        ]
    )
    assert cap.lifted_today(ctx.fold(), T0 + 1)
    assert not cap.lifted_today(ctx.fold(), T0 + 2 * D)
