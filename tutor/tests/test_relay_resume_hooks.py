# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""session_resume, the subject on start / card_done, and the build lane."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

from tutor.curriculum import handlers as cur
from tutor.relay import hooks
from tutor.tests._cur import subject
from tutor.tests._fakes import turn
from tutor.tests._relay_support import engine
from tutor.tests.test_relay_lanes import Rig, run

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from tutor.curriculum.context import Context


def test_resume_kinds(tmp_path: Path) -> None:
    eng, fake = engine(tmp_path, turn("A?"), turn("B?"), turn("after resume"))

    async def script(rig: Rig) -> None:
        got = await rig.send("session_start", {"subject": None, "card": None})
        first = got["data"]["session"]
        got = await rig.send("session_resume", {"session": first})
        assert got["data"] == {"session": first}  # already live
        card = eng.deck[1].id
        got = await rig.send("session_start", {"subject": None, "card": card})
        second = got["data"]["session"]
        got = await rig.send("session_resume", {"session": first})
        assert got["data"] == {"session": first}
        assert fake.closed >= 1
        got = await rig.send("message", {"session": first, "text": "back"})
        assert got["ok"]
        got = await rig.send("session_resume", {"session": "20200101-000000-abcd"})
        assert got["code"] == "bad_request"
        await eng.stop()
        got = await rig.send("session_resume", {"session": first})
        assert got["code"] == "not_live"
        path = eng.store.root / "sessions" / f"{second}.jsonl"
        lines = [json.loads(x) for x in path.read_text().splitlines()]
        lines[0]["card"] = "gone-card"
        path.write_text("".join(json.dumps(x) + "\n" for x in lines))
        got = await rig.send("session_resume", {"session": second})
        assert got["code"] == "bad_request"
        assert "cannot be continued" in got["error"]

    run(eng, script)


def test_subject_reaches_start_and_card_done(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    eng, _ = engine(tmp_path)
    seen: list[Any] = []

    async def start(
        card_id: str | None = None,
        subject: str | None = None,
        *,
        device: str,
        struggling: bool = False,
    ) -> Any:
        assert not struggling
        seen.append(("start", card_id, subject, device))
        return {}

    async def done(card_id: str, *, done: bool, subject: str | None = None) -> Any:
        seen.append(("done", card_id, done, subject))
        return {}

    monkeypatch.setattr(eng, "start", start)
    monkeypatch.setattr(eng, "set_card_done", done)

    async def script(rig: Rig) -> None:
        assert (await rig.send("session_start", {"subject": "car", "card": None}))["ok"]
        body = {"subject": "car", "card": "eng-x", "done": False}
        assert (await rig.send("card_done", body))["ok"]

    run(eng, script)
    assert seen == [("start", None, "car", "desktop"), ("done", "eng-x", False, "car")]


def test_build_lane_runs_the_curriculum_and_publishes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    eng, _ = engine(tmp_path)
    threads: list[str] = []

    def subject_new(body: dict[str, Any], ctx: Context) -> dict[str, Any]:
        threads.append(body["text"])
        subject(ctx, "car")
        return {"subject": "car"}

    def plan_approve(_body: dict[str, Any], _ctx: Context) -> dict[str, Any]:
        code, msg = "plan_conflict", "plan rev moved on"
        raise cur.RequestError(code, msg)

    monkeypatch.setitem(cur.BUILD_HANDLERS, "subject_new", subject_new)
    monkeypatch.setitem(cur.BUILD_HANDLERS, "plan_approve", plan_approve)

    async def script(rig: Rig) -> None:
        got = await rig.send("subject_new", {"text": "cars"})
        assert got == {"ok": True, "data": {"subject": "car"}}
        assert rig.fake.get("tutor/v1/subjects/car/meta/title") == "Cars"
        assert rig.fake.get("tutor/v1/rev/catalog") == 1
        got = await rig.send("plan_approve", {"subject": "car", "plan_rev": 1})
        assert (got["code"], got["error"]) == ("plan_conflict", "plan rev moved on")

    run(eng, script)
    assert threads == ["cars"]


def test_expected_errors() -> None:
    assert hooks.expected(ValueError())
    assert hooks.expected(cur.RequestError("locked", "x"))
    assert not hooks.expected(asyncio.CancelledError())
