# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""C4: ``session_start`` with ``module`` (the lock's ``/learn/<subject>/<module>``).

The session opens on the module's next untaught card, a live or open
session on that module is reused, and everything else is the pick's own
refusal (``no_card_left``): C3 stays the one place that refuses.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tutor.tests._cur import card, make_ctx, module, subject, taught
from tutor.tests._fakes import turn
from tutor.tests._phase import LC, grant
from tutor.tests._relay_support import engine
from tutor.tests.test_relay_lanes import Rig, run

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.engine import Engine


def _lc(root: Path) -> None:
    """LC with ready modules a (a0, a1) and b (b0), and c still generating."""
    ctx, _ = make_ctx(root)
    mods = [module(m, status="ready") for m in ("a", "b")]
    mods.append(module("c", status="generating"))
    found = {"a0": card("a", 0), "a1": card("a", 1), "b0": card("b", 0)}
    subject(ctx, LC, modules=mods, found=found)


def _rig(tmp_path: Path, replies: int = 3) -> Engine:
    eng, _ = engine(tmp_path, *(turn(f"Q{i}?") for i in range(replies)))
    _lc(tmp_path / "data")
    return eng


def _learn(mod: str, **extra: Any) -> dict[str, Any]:
    return {"subject": LC, "module": mod} | extra


def test_a_module_start_teaches_that_modules_next_untaught_card(
    tmp_path: Path,
) -> None:
    grant((LC, "a"), (LC, "b"))
    eng = _rig(tmp_path)

    async def script(rig: Rig) -> None:
        got = await rig.send("session_start", _learn("b"))
        assert got["ok"], got
        assert eng.card is not None
        assert (eng.source.subject, eng.card.id) == (LC, "b0")  # not a0

    run(eng, script)


def test_a_taught_card_is_skipped(tmp_path: Path) -> None:
    grant((LC, "a"))
    eng = _rig(tmp_path)
    taught(eng.ctx, LC, "a0", 1_800_000_000_000)

    async def script(rig: Rig) -> None:
        got = await rig.send("session_start", _learn("a"))
        assert got["ok"], got
        assert eng.card is not None
        assert eng.card.id == "a1"

    run(eng, script)


def test_refused_generating_unknown_and_finished_modules_get_no_card_left(
    tmp_path: Path,
) -> None:
    grant((LC, "a"), (LC, "c"))  # b is refused by C3
    eng = _rig(tmp_path)
    for n, cid in enumerate(("a0", "a1")):
        taught(eng.ctx, LC, cid, 1_800_000_000_000, eid_n=n)

    async def script(rig: Rig) -> None:
        for mod in ("b", "c", "nope", "a"):
            got = await rig.send("session_start", _learn(mod))
            assert not got["ok"], mod
            assert got["code"] == "no_card_left", mod
        assert eng.session_id == ""

    run(eng, script)


def test_a_live_session_on_the_module_is_reused(tmp_path: Path) -> None:
    grant((LC, "a"), (LC, "b"))
    eng, fake = engine(tmp_path, turn("Q1?"), turn("Q2?"))
    _lc(tmp_path / "data")

    async def script(rig: Rig) -> None:
        first = await rig.send("session_start", _learn("a"))
        again = await rig.send("session_start", _learn("a"))
        assert again["data"] == first["data"]
        assert len(fake.prompts) == 1  # no second opening turn

    run(eng, script)


def test_a_live_session_on_another_module_is_not_reused(tmp_path: Path) -> None:
    grant((LC, "a"), (LC, "b"))
    eng = _rig(tmp_path)

    async def script(rig: Rig) -> None:
        first = await rig.send("session_start", _learn("a"))
        other = await rig.send("session_start", _learn("b"))
        assert other["ok"], other
        assert other["data"] != first["data"]
        assert eng.card is not None
        assert eng.card.id == "b0"

    run(eng, script)


def test_an_open_session_on_the_module_is_resumed(tmp_path: Path) -> None:
    grant((LC, "a"), (LC, "b"))
    eng = _rig(tmp_path)

    async def script(rig: Rig) -> None:
        first = await rig.send("session_start", _learn("a"))
        # Another subject goes live; the LC session stays open on disk.
        auto = await rig.send("session_start", {"subject": "automation"})
        assert auto["ok"], auto
        again = await rig.send("session_start", _learn("a"))
        assert again["data"] == first["data"]
        assert eng.source.subject == LC

    run(eng, script)


def test_an_open_session_on_another_module_is_left(tmp_path: Path) -> None:
    grant((LC, "a"), (LC, "b"))
    eng = _rig(tmp_path)

    async def script(rig: Rig) -> None:
        first = await rig.send("session_start", _learn("b"))
        await rig.send("session_start", {"subject": "automation"})
        other = await rig.send("session_start", _learn("a"))
        assert other["ok"], other
        assert other["data"] != first["data"]
        assert eng.card is not None
        assert eng.card.id == "a0"

    run(eng, script)


def test_a_module_start_needs_a_subject_and_no_card(tmp_path: Path) -> None:
    grant((LC, "a"))
    eng = _rig(tmp_path)

    async def script(rig: Rig) -> None:
        for body in (_learn("a", card="a0"), _learn("a", subject=None)):
            got = await rig.send("session_start", body)
            assert got["code"] == "bad_request", body
        assert eng.session_id == ""

    run(eng, script)


def test_the_old_deck_has_no_modules(tmp_path: Path) -> None:
    eng = _rig(tmp_path)

    async def script(rig: Rig) -> None:
        got = await rig.send("session_start", _learn("a", subject="automation"))
        assert got["code"] == "no_card_left"

    run(eng, script)
