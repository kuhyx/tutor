# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Help on a struggling card: ``session_start`` ``struggle`` (struggle contract §5)."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

import pytest

from tutor import struggle
from tutor.cards import Card, Topic
from tutor.curriculum.errors import RequestError
from tutor.curriculum.source import DeckSource, SubjectSource
from tutor.engine import Engine
from tutor.prompt import system_prompt
from tutor.store import Store
from tutor.tests._cur import T0, D, H, card, make_ctx, module, review, subject, taught
from tutor.tests._fakes import FakeSession, ManualClock, turn

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.curriculum.context import Context
    from tutor.session import TutorSession

CARD = Card("io-x", "Q?", "A.", "https://e.org/x", "ex", Topic("io", "I/O", ("io",)))


def _car(root: Path, misses: int = 12) -> Context:
    """Subject ``car``: c0 taught, then Good once and ``misses`` Again; c1 untaught."""
    ctx, _ = make_ctx(root)
    found = {f"c{i}": card("a", i) for i in range(3)}
    subject(ctx, modules=[module("a", status="ready", cards=3)], found=found)
    taught(ctx, "car", "c0", T0 - 30 * D, 1)
    review(ctx, "car", "c0", T0 - 29 * D, 3)
    for i in range(misses):
        review(ctx, "car", "c0", T0 - (misses - i) * D, 1)
    return ctx


def test_the_brief_holds_the_streak_and_the_last_ten_reviews(tmp_path: Path) -> None:
    ctx = _car(tmp_path)
    got = struggle.brief(SubjectSource(Store(tmp_path), ctx, "car"), "c0")
    assert got.count == 12
    assert len(got.reviews) == struggle.LAST_REVIEWS == 10
    assert got.reviews[-1] == (T0 - D, 1)


def test_the_brief_refuses_an_untaught_card_or_the_old_deck(tmp_path: Path) -> None:
    ctx = _car(tmp_path)
    with pytest.raises(RequestError) as err:
        struggle.brief(SubjectSource(Store(tmp_path), ctx, "car"), "c1")
    assert (err.value.code, "not taught" in err.value.message) == ("bad_request", True)
    with pytest.raises(RequestError) as err:
        struggle.brief(DeckSource(Store(tmp_path), []), "c0")
    assert err.value.code == "bad_request"
    src = SubjectSource(Store(tmp_path), ctx, "car")
    with pytest.raises(RequestError) as err:
        struggle.open_card(src, None, struggling=True)
    assert "needs the card" in err.value.message


def test_the_prompt_gets_rule_16_and_the_reviews_only_in_struggle_mode() -> None:
    plain = system_prompt(CARD, [])
    assert "16. " not in plain
    assert "# Struggling card" not in plain
    reviews = ((T0, 3), (T0 + D, 1), (T0 + 2 * D + H, 1))
    text = system_prompt(CARD, [], struggle=struggle.Brief(2, reviews))
    assert "\n16. STRUGGLING CARD." in text
    assert text.index("16. STRUGGLING CARD.") < text.index("# Output")
    assert "rated Again 2 times in a row" in text
    lines = [struggle.when(at) for at, _ in reviews]
    assert f"- {lines[0]}: Good\n- {lines[1]}: Again\n- {lines[2]}: Again\n" in text
    assert "mnemonic" in text
    assert "split" in text


def _engine(root: Path, prompts: list[str]) -> Engine:
    fake = FakeSession(turn("What goes wrong when you recall it?"))

    def factory(prompt: str) -> TutorSession:
        prompts.append(prompt)
        return fake

    return Engine(
        store=Store(root), now=ManualClock(T0 / 1000), session_factory=factory
    )


def test_a_struggle_session_starts_fresh_and_resumes_in_struggle_mode(
    tmp_path: Path,
) -> None:
    _car(tmp_path)
    prompts: list[str] = []
    engine = _engine(tmp_path, prompts)
    asyncio.run(engine.start("c0", subject="car", struggling=True))
    assert "rated Again 12 times in a row" in prompts[-1]
    sid = engine.session_id
    path = tmp_path / "sessions" / f"{sid}.jsonl"
    start = json.loads(path.read_text().splitlines()[0])
    assert (start["type"], start["struggle"]) == ("start", True)
    asyncio.run(engine.close())
    again = _engine(tmp_path, prompts)
    assert again.resume_path(path)
    assert "16. STRUGGLING CARD." in prompts[-1]
    asyncio.run(again.start("c0", subject="car"))  # a plain re-teach: no rule 16
    assert "16. STRUGGLING CARD." not in prompts[-1]
