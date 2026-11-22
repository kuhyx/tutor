# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""C3: the guard's signed ``theory_phase.json`` and the teaching gate it drives.

Only the two GATED LeetCode subjects are gated: the tutor teaches (and marks
taught) a module of theirs only while the guard lists it in ``teachable``.
Anything it cannot trust reads as "nothing teachable", with one warning.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from tutor import drill
from tutor.curriculum import sql_cards, theory_phase
from tutor.curriculum.errors import LOCKED, NO_CARD_LEFT, RequestError
from tutor.curriculum.ids import ulid
from tutor.curriculum.source import SubjectSource
from tutor.store import Store
from tutor.tests._cur import T0, card, make_ctx, module, subject, taught
from tutor.tests._phase import JS, LC, SQL, grant, phase_row, sign, write_phase
from tutor.tests._sql_cards_support import runner

if TYPE_CHECKING:
    from tutor.curriculum.context import Context

_LOGGER = "tutor.curriculum.theory_phase"


def _warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        r.getMessage()
        for r in caplog.records
        if r.name == _LOGGER and r.levelno >= logging.WARNING
    ]


@pytest.fixture(autouse=True)
def _fresh_warnings() -> None:
    """Each test sees its first failure warned (the reader keeps the last one)."""
    theory_phase.forget_failure()


def _src(tmp_path: Path, name: str = LC) -> tuple[Context, SubjectSource]:
    ctx, _ = make_ctx(tmp_path)
    mods = [module("a", status="ready"), module("b", status="ready")]
    found = {"a0": card("a", 0), "a1": card("a", 1), "b0": card("b", 0)}
    subject(ctx, name, modules=mods, found=found)
    return ctx, SubjectSource(Store(tmp_path), ctx, name)


def _code(call: Any, *args: Any, **kw: Any) -> str:
    with pytest.raises(RequestError) as err:
        call(*args, **kw)
    return err.value.code


def test_a_row_signed_by_gatelock_verifies_through_earned_time() -> None:
    grant((LC, "a"), (JS, "js-basics"))
    assert theory_phase.teachable() == frozenset({(LC, "a"), (JS, "js-basics")})


def test_the_gated_subjects_are_the_two_leetcode_ones() -> None:
    assert frozenset({LC, JS}) == theory_phase.GATED


@pytest.mark.parametrize(
    "body",
    [
        None,  # no file at all
        "not json {",
        ["a", "list"],
        {**phase_row([(LC, "a")]), "hmac": "0" * 64},  # bad signature
        {**phase_row([(LC, "a")]), "hmac": "\u00e9"},  # compare_digest raises
        phase_row([(LC, "a")], kind="module_state"),  # wrong kind, signed
        phase_row([(LC, "a")], phase="later"),
        {**phase_row([]), "detail": "flat"},
    ],
    ids=["missing", "garbage", "list", "forged", "ascii", "kind", "phase", "detail"],
)
def test_anything_untrusted_is_nothing_teachable_and_one_warning(
    body: object, caplog: pytest.LogCaptureFixture
) -> None:
    if isinstance(body, str):
        write_phase(None).write_text(body, encoding="utf-8")
    elif body is not None:
        write_phase(body)
    with caplog.at_level(logging.WARNING):
        assert theory_phase.teachable() == frozenset()
    assert len(_warnings(caplog)) == 1


@pytest.mark.parametrize(
    "pairs", [[[LC]], [[LC, 1]], "a,b"], ids=["short", "not-str", "not-list"]
)
def test_a_malformed_teachable_list_is_nothing(
    pairs: object, caplog: pytest.LogCaptureFixture
) -> None:
    row = phase_row([])
    row["detail"]["teachable"] = pairs
    write_phase(sign(row))
    with caplog.at_level(logging.WARNING):
        assert theory_phase.teachable() == frozenset()
    assert len(_warnings(caplog)) == 1


def test_an_unreadable_key_is_nothing_and_one_warning(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    grant((LC, "a"))
    monkeypatch.setenv("TUTOR_KEY", str(tmp_path / "missing.key"))
    with caplog.at_level(logging.WARNING):
        assert theory_phase.teachable() == frozenset()
    assert len(caplog.records) == 1  # not a second line from the key reader


def test_a_repeated_failure_is_warned_once_until_it_changes(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The server reads on every publish: one line per failure, not per read."""
    with caplog.at_level(logging.WARNING):
        for _ in range(3):  # missing file, three reads
            assert theory_phase.teachable() == frozenset()
        assert len(_warnings(caplog)) == 1
        write_phase(sign(phase_row([(LC, "a")])) | {"hmac": "0" * 64})
        theory_phase.teachable()
        theory_phase.teachable()
        assert len(_warnings(caplog)) == 2  # a different failure: one more
        grant((LC, "a"))
        assert theory_phase.teachable() == {(LC, "a")}
        write_phase({}).unlink()
        theory_phase.teachable()
    assert len(_warnings(caplog)) == 3  # after a good read it is news again


def test_a_valid_solve_row_is_nothing_without_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    write_phase(phase_row([], phase="solve"))
    with caplog.at_level(logging.WARNING):
        assert theory_phase.teachable() == frozenset()
    assert _warnings(caplog) == []


def test_only_the_theory_phase_grants_anything() -> None:
    write_phase(phase_row([(LC, "a")], phase="solve"))  # contradictory: ignored
    assert theory_phase.teachable() == frozenset()


def test_solve_refuses_every_gated_module(tmp_path: Path) -> None:
    write_phase(phase_row([], phase="solve"))
    ctx, src = _src(tmp_path)
    assert _code(src.pick, None) == NO_CARD_LEFT
    assert _code(src.pick, "b0") == NO_CARD_LEFT
    assert _code(src.mark, "a0", "s1", done=True) == LOCKED
    assert ctx.fold().taught_ids(LC) == set()


def test_a_missing_phase_file_refuses_the_js_subject_too(tmp_path: Path) -> None:
    _, src = _src(tmp_path, JS)
    assert _code(src.pick, None) == NO_CARD_LEFT


def test_theory_teaches_only_the_listed_module(tmp_path: Path) -> None:
    grant((LC, "b"))
    ctx, src = _src(tmp_path)
    assert src.pick(None).id == "b0"  # a comes first in the plan, and is refused
    assert _code(src.pick, "a0") == NO_CARD_LEFT
    assert _code(src.mark, "a1", "s1", done=True) == LOCKED
    src.mark("b0", "s1", done=True)
    assert ctx.fold().taught_ids(LC) == {"b0"}
    assert _code(src.pick, None) == NO_CARD_LEFT  # b is fully taught, a refused
    assert src.pick("b0").id == "b0"  # re-teaching a taught card of b: allowed


def test_a_refused_card_never_offers_the_daily_cap_lift(tmp_path: Path) -> None:
    grant()  # THEORY of nothing
    ctx, src = _src(tmp_path)
    eid = ulid(T0, bytes([9] * 10))
    ctx.log.append([{"k": "new_cap", "n": 1, "at": T0, "dev": "phone", "eid": eid}])
    taught(ctx, "other", "x", T0)
    assert _code(src.pick, "a0") == NO_CARD_LEFT


@pytest.mark.parametrize("name", [SQL, "car"])
def test_an_ungated_subject_never_reads_the_phase(
    name: str, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    ctx, src = _src(tmp_path, name)  # no phase file at all
    with caplog.at_level(logging.WARNING):
        assert src.pick(None).id == "a0"
        src.mark("a0", "s1", done=True)
    assert ctx.fold().taught_ids(name) == {"a0"}
    assert _warnings(caplog) == []


def test_a_taught_card_of_a_refused_module_still_drills_and_reviews(
    tmp_path: Path,
) -> None:
    ctx, src = _src(tmp_path)
    taught(ctx, LC, "a0", T0, 1)
    write_phase(phase_row([], phase="solve"))
    got = drill.Drill(Store(tmp_path), ctx).next(LC, T0 / 1000 + 30 * 86_400)
    assert got["card"]["id"] == "a0"
    at = T0 + 86_400_000
    review = {"k": "review", "s": LC, "c": "a0", "r": 3, "rev": 1, "at": at}
    ctx.log.append([review | {"dev": "phone", "eid": ulid(at, bytes([8] * 10))}])
    assert ctx.fold().card(LC, "a0").reviews
    assert "a0" in src.done()
    src.mark("a0", "s1", done=False)  # taking a card back is never gated
    assert ctx.fold().taught_ids(LC) == set()


def test_the_sql_seeder_never_teaches_a_refused_module(tmp_path: Path) -> None:
    ctx, _ = make_ctx(tmp_path)
    subject(ctx, LC, modules=[module("select-group-basics", status="ready")])
    got = sql_cards.seed_concept(ctx, "NULL comparisons", runner, subject=LC)
    assert got.added
    assert got.taught == []
    grant((LC, sql_cards.MODULE))
    again = sql_cards.seed_concept(ctx, "NULL comparisons", runner, subject=LC)
    assert again.taught == got.added


def test_the_plan_overlay_marks_each_gated_module(
    caplog: pytest.LogCaptureFixture,
) -> None:
    grant((LC, "b"))
    plan = {"rev": 1, "modules": [{"id": "a"}, {"id": "b"}]}
    assert theory_phase.overlay(LC, plan) == {
        "rev": 1,
        "modules": [{"id": "a", "teachable": False}, {"id": "b", "teachable": True}],
    }
    with caplog.at_level(logging.WARNING):
        assert theory_phase.overlay(SQL, plan) is plan
        assert theory_phase.overlay(LC, None) is None  # a plan still drafting
    assert _warnings(caplog) == []


def test_the_default_path_is_the_guards_data_dir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TUTOR_THEORY_PHASE")
    want = Path.home() / ".local/share/leetcode_guard/theory_phase.json"
    assert theory_phase.phase_path() == want
