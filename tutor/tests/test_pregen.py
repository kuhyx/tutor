# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Pre-generating a locked module: cards ahead of time, study order kept."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from tutor.curriculum import cap, cardgen, handlers, judge, rules, wiki
from tutor.curriculum.errors import RequestError
from tutor.curriculum.records import Module, Plan, plan_json
from tutor.curriculum.source import SubjectSource
from tutor.store import Store
from tutor.tests._cur import T0, H, card, make_ctx, module, review, subject, taught

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.curriculum.context import Context
    from tutor.tests._cur import Fakes

SOURCES = [
    wiki.Source("https://en.wikipedia.org/wiki/A", "A", "text a"),
    wiki.Source("https://en.wikibooks.org/wiki/B", "B", "text b"),
]
A_CARDS = ("a-1", "a-2", "a-3")


def drafted(n: int) -> dict[str, Any]:
    """A model answer with ``n`` valid cards."""
    return {
        "cards": [
            {
                "id": f"bee-{i}",
                "front": f"What does part {i} do?",
                "back": "It turns.",
                "source": 1 + i % 2,
                "excerpt": f"part {i} turns the crank shaft round and round",
                "requires": [],
            }
            for i in range(n)
        ]
    }


@pytest.fixture
def pre(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Context, Fakes]:
    """``a`` ready (3 untaught cards), ``b`` needs a, ``c`` needs b."""
    ctx, fakes = make_ctx(tmp_path)
    monkeypatch.setattr(cardgen, "_sources", lambda *_: list(SOURCES))
    monkeypatch.setattr(judge, "gate", lambda _c, _s, cards, _t, _k: (cards, []))
    found = {cid: card("a", n) for n, cid in enumerate(A_CARDS, 1)}
    subject(
        ctx,
        modules=[
            module("a", status="ready", cards=3),
            module("b", "a"),
            module("c", "b"),
        ],
        found=found,
    )
    return ctx, fakes


def pregen(ctx: Context, modules: object) -> dict[str, Any]:
    body = {"subject": "car", "modules": modules}
    return handlers.BUILD_HANDLERS["module_pregenerate"](body, ctx)


def mod(ctx: Context, mid: str) -> Module:
    plan = ctx.subjects.plan("car")
    assert plan is not None
    found = plan.module(mid)
    assert found is not None
    return found


def view(ctx: Context) -> rules.View:
    plan = ctx.subjects.plan("car")
    assert plan is not None
    return rules.View("car", plan, ctx.subjects.cards("car"))


def master_a(ctx: Context) -> None:
    for n, cid in enumerate(A_CARDS):
        taught(ctx, "car", cid, T0 + n, n)
        review(ctx, "car", cid, T0 + 21 * H + n, 3)


def b_cards(ctx: Context) -> list[str]:
    return [cid for cid, c in ctx.subjects.cards("car").items() if c.module == "b"]


def test_pregenerated_module_has_cards_but_stays_locked(
    pre: tuple[Context, Fakes], tmp_path: Path
) -> None:
    ctx, fakes = pre
    assert pregen(ctx, ["b"]) == {"queued": ["b"]}
    assert (mod(ctx, "b").status, mod(ctx, "b").pregenerated) == ("generating", True)
    assert handlers.pending(ctx) == [("car", "b")]
    fakes.replies.append(drafted(4))
    got = handlers.generate(ctx, "car", "b")
    assert (got["status"], got["cards"]) == ("locked", 4)
    assert b_cards(ctx) == ["bee-0", "bee-1", "bee-2", "bee-3"]
    assert handlers.fold_and_advance(ctx)["generate"] == []
    assert mod(ctx, "b").status == "locked"
    # Never offered, never startable, never counted as new.
    folded = ctx.fold()
    with pytest.raises(RequestError) as err:
        rules.pick(view(ctx), folded, "bee-0", ctx.clock())
    assert err.value.code == "locked"
    for n, cid in enumerate(A_CARDS):
        taught(ctx, "car", cid, T0 + n, n)
    with pytest.raises(RequestError) as err:
        rules.pick(view(ctx), ctx.fold(), None, ctx.clock())
    assert err.value.code == "no_card_left"
    assert cap.new_today(ctx.fold(), ctx.clock()) == 3  # a's only
    # A manual "card done" cannot teach it either (it would open the module).
    source = SubjectSource(Store(tmp_path / "store"), ctx, "car")
    with pytest.raises(RequestError) as err:
        source.mark("bee-0", "manual", done=True)
    assert err.value.code == "locked"
    assert not ctx.fold().card("car", "bee-0").taught
    source.mark("bee-0", "manual", done=False)  # taking back is always allowed


def test_mastered_requires_open_it_without_generating_again(
    pre: tuple[Context, Fakes],
) -> None:
    ctx, fakes = pre
    pregen(ctx, ["b"])
    fakes.replies.append(drafted(4))
    handlers.generate(ctx, "car", "b")
    before, calls = b_cards(ctx), len(fakes.prompts)
    master_a(ctx)
    out = handlers.fold_and_advance(ctx)
    assert out["generate"] == []
    b = mod(ctx, "b")
    assert (b.status, b.pregenerated, b.cards) == ("ready", False, 4)
    assert mod(ctx, "a").status == "mastered"
    assert mod(ctx, "c").status == "locked"
    assert b_cards(ctx) == before
    assert len(fakes.prompts) == calls
    assert handlers.pending(ctx) == []
    assert rules.pick(view(ctx), ctx.fold(), None, ctx.clock()) == "bee-0"


def test_generation_finishing_after_unlock_opens_it(
    pre: tuple[Context, Fakes],
) -> None:
    ctx, fakes = pre
    pregen(ctx, ["b"])
    master_a(ctx)
    handlers.fold_and_advance(ctx)  # a mastered while b was still generating
    fakes.replies.append(drafted(3))
    assert handlers.generate(ctx, "car", "b")["status"] == "ready"
    assert mod(ctx, "b").pregenerated is False


def test_failed_pregeneration_retries_locked_and_falls_back_on_unlock(
    pre: tuple[Context, Fakes],
) -> None:
    ctx, fakes = pre
    pregen(ctx, ["b"])
    fakes.replies.append(drafted(1))  # too few cards
    assert handlers.generate(ctx, "car", "b")["status"] == "failed"
    assert mod(ctx, "b").pregenerated is True
    handlers.fold_and_advance(ctx)
    assert mod(ctx, "b").status == "failed"
    # plan_approve retries it; still locked for study afterwards.
    handlers.BUILD_HANDLERS["plan_approve"]({"subject": "car", "plan_rev": 1}, ctx)
    assert mod(ctx, "b").status == "generating"
    fakes.replies.append(drafted(1))
    handlers.generate(ctx, "car", "b")
    # Unlocking a failed pre-generation drafts just in time, as without it.
    master_a(ctx)
    assert handlers.fold_and_advance(ctx)["generate"] == [["car", "b"]]
    assert (mod(ctx, "b").status, mod(ctx, "b").pregenerated) == ("generating", False)
    fakes.replies.append(drafted(3))
    assert handlers.generate(ctx, "car", "b")["status"] == "ready"


def test_all_queues_every_locked_module_once(pre: tuple[Context, Fakes]) -> None:
    ctx, _ = pre
    assert pregen(ctx, "all") == {"queued": ["b", "c"]}
    assert handlers.pending(ctx) == [("car", "b"), ("car", "c")]
    assert pregen(ctx, "all") == {"queued": []}  # nothing locked is left


@pytest.mark.parametrize(
    ("modules", "code"),
    [
        (["a"], "bad_request"),  # ready, not locked
        (["b", "zz"], "bad_request"),  # unknown module
        ([], "bad_request"),
        (["b", "b"], "bad_request"),
        ("some", "bad_request"),
        (["Bad id"], "bad_request"),
    ],
)
def test_refusals_write_nothing(
    pre: tuple[Context, Fakes], modules: object, code: str
) -> None:
    ctx, _ = pre
    rev = ctx.subjects.need_meta("car").rev
    with pytest.raises(RequestError) as err:
        pregen(ctx, modules)
    assert err.value.code == code
    assert ctx.subjects.need_meta("car").rev == rev
    assert mod(ctx, "b").status == "locked"


def test_refused_when_already_pregenerated_or_plan_not_approved(
    pre: tuple[Context, Fakes],
) -> None:
    ctx, fakes = pre
    pregen(ctx, ["b"])
    fakes.replies.append(drafted(3))
    handlers.generate(ctx, "car", "b")
    with pytest.raises(RequestError, match="already pre-generated") as err:
        pregen(ctx, ["b"])
    assert err.value.code == "bad_request"
    assert pregen(ctx, "all") == {"queued": ["c"]}
    subject(ctx, "draft-one", plan_status="draft", status="draft")
    with pytest.raises(RequestError) as err:
        handlers.BUILD_HANDLERS["module_pregenerate"](
            {"subject": "draft-one", "modules": "all"}, ctx
        )
    assert err.value.code == "plan_conflict"
    for name in ("nope", "Bad!"):
        with pytest.raises(RequestError) as err:
            handlers.BUILD_HANDLERS["module_pregenerate"](
                {"subject": name, "modules": "all"}, ctx
            )
        assert err.value.code == "bad_request"


def test_flag_round_trip_and_wire_shape() -> None:
    plan = Plan(
        1, "approved", "", [Module("b", "B", pregenerated=True), Module("c", "C")]
    )
    out = plan_json(plan)
    assert out["modules"][0]["pregenerated"] is True
    assert "pregenerated" not in out["modules"][1]  # the old shape when unset
    assert Plan.from_json(out) == plan
    client = Module.from_json(
        {"id": "b", "title": "B", "pregenerated": True}, client=True
    )
    assert client.pregenerated is False
