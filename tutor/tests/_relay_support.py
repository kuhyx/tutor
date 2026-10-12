# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Shared relay test wiring: a scripted engine, the fake RTDB, a Wiring."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tutor.curriculum.context import Context
from tutor.engine import Engine
from tutor.relay.context import Wiring
from tutor.relay.curriculum_sync import CurriculumSync
from tutor.relay.done import DoneMap
from tutor.relay.lanes import Server
from tutor.relay.phases import PhaseSink
from tutor.relay.projection import Publisher
from tutor.store import Store
from tutor.tests._cur import Fakes
from tutor.tests._fakes import FakeCredit, FakeSession, ManualClock

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.models import TutorTurn
    from tutor.tests._fake_rtdb import FakeRtdb

WORKER = "139581a6-25fa-4cd5-ba30-debb1c796682"
PHONE = "107cb1bf-a093-416a-b356-a995e13f73fe"
RIDS = [f"01M4RBCX52MMHCK7K73E6KV9{n:02d}" for n in range(10, 40)]


class RelayEngine(Engine):
    """An engine whose curriculum context never reaches a model or the web."""

    fakes = Fakes()

    @property
    def ctx(self) -> Context:
        """The data dir with faked model / fetch / check and the worker's id."""
        f = self.fakes
        return Context(
            self.store.root,
            clock=lambda: int(self.time() * 1000),
            model=f.model,
            fetch=f.fetch,
            check=f.check,
            device=WORKER,
        )


def engine(
    tmp_path: Path, *replies: TutorTurn | Exception, clock: ManualClock | None = None
) -> tuple[Engine, FakeSession]:
    """An engine on ``tmp_path/data`` answering with ``replies``."""
    fake = FakeSession(*replies)
    data = tmp_path / "data"
    data.mkdir(parents=True, exist_ok=True)
    (data / "device_id").write_text(WORKER + "\n")  # the worker's own id
    eng = RelayEngine(
        store=Store(data),
        now=clock or ManualClock(),
        credit_fn=FakeCredit(),
        session_factory=lambda _prompt: fake,
    )
    eng.fakes = Fakes()
    return eng, fake


def wiring(fake: FakeRtdb, eng: Engine, now: Any = None) -> Wiring:
    """Everything the relay shares, on the fake database."""
    clock = now or eng.time
    rtdb = fake.rtdb()
    done = DoneMap(eng.store.root / "requests_done.jsonl", clock())
    publisher = Publisher(rtdb, eng, done, resolve_url=lambda _page: None)
    return Wiring(rtdb, eng, publisher, done, PhaseSink(), WORKER, clock)


def server(w: Wiring) -> Server:
    """A lane server with its curriculum sync."""
    return Server(w, CurriculumSync(w))


def request(kind: str, body: dict[str, Any], *, created: int = 0) -> dict[str, Any]:
    """A client ``req`` node."""
    return {"kind": kind, "dev": PHONE, "created": created, "body": body}
