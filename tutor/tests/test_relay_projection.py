# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The projection: views rebuilt from transcripts and the publisher's writes."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

from tutor import history
from tutor.delivery import Delivery
from tutor.relay import views
from tutor.tests._fake_rtdb import FakeRtdb
from tutor.tests._fakes import turn
from tutor.tests._relay_support import PHONE, RIDS, engine, wiring

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.engine import Engine

IMG = {
    "term": "coil",
    "title": "Coil.jpg",
    "file": "0123456789abcdef.jpg",
    "author": "A",
    "licence": "PD",
    "licence_url": "",
    "page_url": "https://commons.wikimedia.org/wiki/File:Coil.jpg",
    "url": "https://upload.wikimedia.org/x/800px-Coil.jpg",
}


def studied(tmp_path: Path) -> Engine:
    """A session: tutor, learner (rid), tutor with a picture, a failed reply."""
    eng, _ = engine(tmp_path, turn("Q1?"), turn("Good. Q2?"), RuntimeError("cli died"))
    asyncio.run(eng.start())
    asyncio.run(
        eng.reply("an answer", msg_id=RIDS[0], via=Delivery(received=eng.time()))
    )
    eng.messages[-1]["images"] = [IMG]  # as media.attach would have put it
    sid = eng.session_id
    path = eng.store.root / "sessions" / f"{sid}.jsonl"
    lines = path.read_text().splitlines()
    last = json.loads(lines[-1])
    last["ui"]["images"] = [IMG]
    path.write_text("\n".join([*lines[:-1], json.dumps(last), "{cut"]) + "\n")
    eng.store.log(sid, {"type": "learner", "text": "lost", "msg_id": "x"})
    return eng


def src(eng: Engine) -> views.Sources:
    view = history.View({c.id: c.front for c in eng.deck}, eng.session_id, set(), set())
    return views.Sources(
        view, eng.time(), lambda rid: PHONE if rid else None, lambda _p: None
    )


def test_build_session_doc(tmp_path: Path) -> None:
    eng = studied(tmp_path)
    doc = views.build(eng.store.root / "sessions", eng.session_id, src(eng))
    assert doc is not None
    assert list(doc.msgs) == ["m0001", "m0002", "m0003"]
    learner = doc.msgs["m0002"]
    assert learner == {
        "role": "learner",
        "text": "an answer",
        "at": learner["at"],
        "rid": RIDS[0],
        "dev": PHONE,
    }
    tutor = doc.msgs["m0003"]
    assert tutor["images"][0]["url"].startswith("https://upload.wikimedia.org/")
    assert tutor["diagrams"] == []
    assert doc.meta["n"] == 3
    assert doc.meta["clock"]["awaiting_since"] == tutor["at"]
    assert doc.meta["busy"] is None
    assert doc.meta["subject"] == "automation"
    assert doc.rev == views.transcript_rev(eng.store.root / "sessions", eng.session_id)
    assert doc.index["rev"] == doc.rev
    assert doc.index["cards"][0]["id"] == doc.meta["card"]["id"]


def test_build_none_for_unknown_sessions(tmp_path: Path) -> None:
    eng, _ = engine(tmp_path)
    sessions = eng.store.root / "sessions"
    assert views.build(sessions, "20260101-000000-abcd", src(eng)) is None
    assert views.build(sessions, "../x", src(eng)) is None
    assert views.transcript_rev(sessions, "20260101-000000-abcd") == 0


def test_messages_pairing_without_logged_times(tmp_path: Path) -> None:
    eng = studied(tmp_path)
    conv = eng._conv
    assert conv is not None
    events = [
        {"type": "learner", "logged_at": "2026-10-12T10:00:00+00:00"},
        {"type": "next_card"},
        {"type": "stop"},
        {"type": "credit"},
    ]
    conv.messages.append({"role": "card", "text": "next", "card_id": "x"})
    got = views.messages(conv, events, src(eng))
    assert got[0]["at"] is None  # more messages than logged turns
    assert got[1] == {"role": "learner", "text": "an answer", "at": None}
    assert got[-1] == {"role": "card", "text": "next", "card_id": "x"}
    assert views._t({"logged_at": "2026-10-12T10:00:00+00:00"}) == 1791799200000
    assert views.key("r", 3) == "r0003"


def test_publisher_startup_republishes_stale_and_tracks_live(tmp_path: Path) -> None:
    eng = studied(tmp_path)
    sid = eng.session_id
    (eng.store.root / "sessions" / "not-a-session.jsonl").write_text("{}\n")
    fake = FakeRtdb()

    async def go() -> None:
        w = wiring(fake, eng)
        pub = w.publisher
        assert await pub.startup() == 1
        meta = fake.get(f"tutor/v1/sessions/{sid}/meta")
        assert meta["n"] == 3
        assert fake.get("tutor/v1/live")["session"] == sid
        assert fake.get("tutor/v1/rev/stats") == 1
        assert fake.get("tutor/v1/stats/today/new_cap") == 10
        assert await pub.startup() == 0  # up to date
        fake.set("tutor/v1/session_index/" + sid + "/rev", "junk")
        assert await pub.startup() == 1
        fake.log.clear()
        await pub.live()  # unchanged: no write
        await pub.stats()
        assert fake.log == []
        await w.rtdb.aclose()

    asyncio.run(go())


def test_publisher_appends_only_new_messages(tmp_path: Path) -> None:
    eng, _ = engine(tmp_path, turn("Q1?"), turn("Q2?"), turn("Q3?"))
    fake = FakeRtdb()

    async def go() -> None:
        w = wiring(fake, eng)
        pub = w.publisher
        await eng.start()
        sid = eng.session_id
        await pub.after({sid, ""})
        assert set(fake.get(f"tutor/v1/sessions/{sid}/msgs")) == {"m0001"}
        await eng.reply("a", msg_id=RIDS[1])
        fake.log.clear()
        await pub.after({sid})
        assert ("PATCH", f"/sessions/{sid}/msgs") in fake.log
        assert ("PUT", f"/sessions/{sid}/msgs") not in fake.log
        assert set(fake.get(f"tutor/v1/sessions/{sid}/msgs")) == {
            "m0001",
            "m0002",
            "m0003",
        }
        fake.log.clear()
        await pub.session(sid)  # nothing new: meta + receipts + index only
        assert ("PATCH", f"/sessions/{sid}/msgs") not in fake.log
        await pub.session(sid, full=True)
        assert ("PUT", f"/sessions/{sid}/msgs") in fake.log
        # A web-page turn: refresh notices the transcript grew.
        await eng.reply("b", msg_id="page-1")
        fake.log.clear()
        await pub.refresh()
        assert ("PATCH", f"/sessions/{sid}/msgs") in fake.log
        fake.log.clear()
        await pub.refresh()
        assert all(p != f"/sessions/{sid}/meta" for _, p in fake.log)
        await eng.stop()
        await pub.refresh()
        assert fake.get("tutor/v1/live") is None
        await w.rtdb.aclose()

    asyncio.run(go())


def test_publisher_skips_missing_and_migrates_archived(tmp_path: Path) -> None:
    eng = studied(tmp_path)
    eng.store.archive("20261001-100000-abcd")
    eng.store.archive("bad id")
    fake = FakeRtdb()

    async def go() -> None:
        w = wiring(fake, eng)
        await w.publisher.session("20260101-000000-abcd")
        assert fake.get("tutor/v1/sessions") is None
        assert await w.publisher.archived() == 1
        assert fake.get("tutor/v1/sessions/20261001-100000-abcd/user") == {
            "archived": True
        }
        assert w.publisher.sessions_dir == eng.store.root / "sessions"
        await w.rtdb.aclose()

    asyncio.run(go())


def test_card_edit_notices_reach_the_tutor_message(tmp_path: Path) -> None:
    eng = studied(tmp_path)
    conv = eng._conv
    assert conv is not None
    conv.messages[-1]["notices"] = ["Card removed: What is a coil?"]
    got = views.messages(conv, [], src(eng))
    assert got[-1]["notices"] == ["Card removed: What is a coil?"]
    assert "notices" not in got[0]
