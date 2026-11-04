# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Own events stay readable from a cursor: a backdated eid is re-minted."""

from __future__ import annotations

import asyncio
import dataclasses
from typing import TYPE_CHECKING

from tutor.curriculum.eventlog import worker_event
from tutor.curriculum.ids import ulid
from tutor.relay.curriculum_sync import CurriculumSync
from tutor.tests._fake_rtdb import FakeRtdb
from tutor.tests._relay_support import PHONE, WORKER, engine, wiring

if TYPE_CHECKING:
    from pathlib import Path

T = 1_800_000_000_000
DAY = 86_400_000


def _outside(card: str, at: int) -> dict[str, object]:
    """A ``taught`` minted by another process (``sql-cards``, a seeding
    script): its eid comes from the backdated ``at``, not after the worker's."""
    return {
        **worker_event("taught", ("cram", card), dev=WORKER, at=at),
        "eid": ulid(at, b"\x01" * 10),
    }


def test_backdated_teach_reaches_a_reader_past_it(tmp_path: Path) -> None:
    """2026-11-04: 37 cram cards taught 3 days back from outside the server.
    The PC counted "37 due"; the app, whose cursor on ``log/{pc}`` was already
    past their eids, never fetched them and showed "Nothing due"."""
    pc, _ = engine(tmp_path / "pc")
    phone, _ = engine(tmp_path / "phone")
    fake = FakeRtdb()
    sync = CurriculumSync(wiring(fake, pc))
    reader = CurriculumSync(dataclasses.replace(wiring(fake, phone), worker=PHONE))
    pc.ctx.log.append([worker_event("taught", ("car", "a-1"), dev=WORKER, at=T)])

    async def go() -> None:
        await sync.push()
        assert await reader.pull() == 1  # the reader's cursor: that eid
        pc.ctx.log.append([_outside("lps-loops", T - 3 * DAY)])
        await sync.push()
        await reader.pull()
        await sync.w.rtdb.aclose()
        await reader.w.rtdb.aclose()

    asyncio.run(go())
    assert pc.ctx.fold().taught_ids("cram") == {"lps-loops"}
    assert phone.ctx.fold().taught_ids("cram") == {"lps-loops"}
    due = phone.ctx.fold().card("cram", "lps-loops").fsrs_state()
    assert due == pc.ctx.fold().card("cram", "lps-loops").fsrs_state()


def _ev(kind: str, eid_at: int, dev: str = "pc", card: str = "c1") -> dict[str, object]:
    return {
        "k": kind,
        "s": "cram",
        "c": card,
        "at": eid_at,
        "dev": dev,
        "eid": ulid(eid_at, b"\x02" * 10),
    }


def test_in_order_log_needs_no_copy() -> None:
    from tutor.curriculum import log_order

    events = [_ev("taught", T), _ev("taught", T + 1, card="c2")]
    assert log_order.copies(events, "pc", T + 5) == []


def test_stranded_teach_is_reminted_above_every_own_eid() -> None:
    from tutor.curriculum import log_order
    from tutor.curriculum.ids import ulid_ms

    late = _ev("taught", T - DAY, card="old")
    events = [_ev("taught", T), late, _ev("taught", T, dev="phone", card="x")]
    out = log_order.copies(events, "pc", 0)
    assert [e["c"] for e in out] == ["old"]
    assert out[0]["at"] == T - DAY
    assert ulid_ms(out[0]["eid"]) > T
    assert log_order.copies([*events, *out], "pc", 0) == []


def test_stranded_review_is_logged_not_copied(caplog: object) -> None:
    from tutor.curriculum import log_order

    events = [_ev("taught", T), _ev("review", T - DAY)]
    assert log_order.copies(events, "pc", T + 5) == []
