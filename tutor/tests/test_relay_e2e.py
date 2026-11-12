# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""End-to-end encryption: nothing the relay writes to RTDB is readable there."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import TYPE_CHECKING

from crdt_sync import Argon2Params, E2eCipher, E2eKey, E2eLockedError
import pytest

from tutor.relay import config, e2e, sse, worker
from tutor.relay.config import passphrase as unpatched_passphrase
from tutor.relay.phases import PhaseSink
from tutor.tests._fake_rtdb import FakeRtdb
from tutor.tests._fakes import turn
from tutor.tests._relay_support import engine, wiring

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from tutor.relay.rtdb import Rtdb

FAST = Argon2Params(memory_kib=8, iterations=1, parallelism=1)


def test_published_session_is_ciphertext_at_rest(tmp_path: Path) -> None:
    eng, _ = engine(tmp_path, turn("What does a relay coil do?"))
    asyncio.run(eng.start())
    sid = eng.session_id
    fake = FakeRtdb()

    async def go() -> None:
        w = wiring(fake, eng)
        await w.publisher.startup()
        await w.rtdb.aclose()

    asyncio.run(go())
    at_rest = json.dumps(fake.raw[e2e.ROOT.split("/")[0]])
    assert "relay coil" not in at_rest
    assert '"text"' not in at_rest
    assert '"role"' not in at_rest
    # The relay itself reads it back in the clear.
    assert fake.get(f"{e2e.ROOT}/sessions/{sid}/msgs/m0001")["text"].startswith(
        "What does a relay coil"
    )


VECTORS = json.loads(
    (Path(__file__).parents[2] / "contract" / "e2e_vectors.json").read_text()
)


def _sealer() -> e2e.Sealer:
    return e2e.Sealer(E2eCipher(bytes.fromhex(VECTORS["key_hex"])))


def test_vectors_pin_the_rules_and_open() -> None:
    assert VECTORS["root"] == e2e.ROOT == "tutor/v1-e2e"
    for rule in VECTORS["rules"]:
        assert e2e.classify(e2e.parts_of(rule["path"])).kind == rule["kind"], rule
    s = _sealer()
    for unit in VECTORS["units"]:
        assert s.open(unit["path"], unit["stored"]) == unit["value"]
        assert set(unit["stored"]) - {e2e.SEALED} <= {"created", "at", "seen", "beat"}


def test_seal_refuses_unknown_and_inside_unit_writes() -> None:
    s = _sealer()
    with pytest.raises(e2e.E2eLayoutError):
        s.seal("secrets", {"a": 1})
    with pytest.raises(e2e.E2eLayoutError):
        s.seal("sessions", "flat")  # a scalar where a tree belongs
    with pytest.raises(e2e.E2eLayoutError):
        s.seal_patch("sessions/s/msgs/m0001", {"text": "x"})
    with pytest.raises(e2e.E2eLayoutError):
        s.open("stats/today/x", 1)
    assert e2e.unit_path("stats/today/x") == "stats/today"
    assert e2e.unit_path("stats/today") is None


def test_open_drops_a_moved_or_tampered_unit_and_keeps_plaintext() -> None:
    s = _sealer()
    sealed = s.seal("prefs/current_subject", "car")
    assert s.open("prefs", {"current_subject": sealed}) == {"current_subject": "car"}
    # The AAD binds a blob to its path: copied elsewhere it does not open.
    assert s.open("prefs", {"other": sealed}) == {}
    assert s.open("prefs", {"current_subject": {e2e.SEALED: "AQ=="}}) == {}
    # Legacy plaintext (no `_e2e`) still reads during the migration.
    assert s.open("prefs/current_subject", "car") == "car"
    assert s.open("sessions", [{"x": 1}]) == [{"x": 1}]


def test_rtdb_reads_below_a_unit_and_streams_open(tmp_path: Path) -> None:
    fake = FakeRtdb()
    fake.set(f"{e2e.ROOT}/stats/today", {"new_cap": 25})

    async def go() -> None:
        db = fake.rtdb()
        assert await db.get("stats/today/new_cap") == 25
        assert await db.get("stats/today/nope/deeper") is None
        stream = sse.listen(db, "stats")
        first = await anext(stream)
        assert first.data == {"today": {"new_cap": 25}}
        await db.patch("stats", {"days": {"2026-11-12": {"m": 3}}})
        second = await anext(stream)
        assert second.kind == "patch"
        assert second.data == {"days": {"2026-11-12": {"m": 3}}}
        await stream.aclose()
        await db.aclose()

    asyncio.run(go())
    assert "new_cap" not in json.dumps(fake.raw)


def test_unlock_creates_the_header_then_refuses_a_wrong_passphrase() -> None:
    fake = FakeRtdb(sealed=False)

    async def go() -> None:
        db = fake.rtdb()
        key = await e2e.unlock(db, "pw", FAST)
        header = fake.raw_get(e2e.LAYOUT.e2e_path)
        assert isinstance(header, str)
        assert "argon2id" in header
        again = await e2e.unlock(db, "pw", FAST)
        assert again.master == key.master
        with pytest.raises(E2eLockedError):
            await e2e.unlock(db, "other", FAST)
        with pytest.raises(E2eLockedError):
            await e2e.unlock(db, "", FAST)
        fake.raw_set(e2e.LAYOUT.e2e_path, {"not": "a header"})
        with pytest.raises(E2eLockedError):
            await e2e.unlock(db, "pw", FAST)
        await db.aclose()

    asyncio.run(go())


def test_config_seal_and_connect_sealed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeRtdb(sealed=False)
    pw = tmp_path / "password"
    assert config.read_passphrase(pw) == ""
    pw.write_text("pw\n")
    assert config.read_passphrase(pw) == "pw"
    assert config.password_file() == Path.home() / ".config/crdt-sync/password"
    with pytest.raises(AssertionError, match="inject a passphrase"):
        config.passphrase()  # the conftest guard

    async def go() -> None:
        db = await config.seal(fake.rtdb(), "pw", FAST)
        assert db.sealer is not None
        await db.put("prefs/current_subject", "car")
        assert fake.raw_get(f"{e2e.ROOT}/prefs/current_subject")[e2e.SEALED]
        await db.aclose()
        monkeypatch.setattr(config, "connect", fake.rtdb)
        monkeypatch.setattr(config, "passphrase", lambda: "")
        with pytest.raises(config.RelaySetupError):
            await config.connect_sealed()
        sealed = await config.connect_sealed("pw")
        assert sealed.sealer is not None
        await sealed.aclose()

    monkeypatch.setattr(e2e, "unlock", _fast_unlock(e2e.unlock))
    asyncio.run(go())


def _fast_unlock(
    real: Callable[[Rtdb, str, Argon2Params | None], Awaitable[E2eKey]],
) -> Callable[..., Awaitable[E2eKey]]:
    async def unlock(
        db: Rtdb, secret: str, params: Argon2Params | None = None
    ) -> E2eKey:
        return await real(db, secret, params or FAST)

    return unlock


def test_migrate_copies_client_owned_nodes_once_and_fences_old_clients() -> None:
    fake = FakeRtdb()
    old = e2e.OLD_ROOT
    fake.raw_set(f"{old}/meta", {"schema": 1, "min_client": 1})
    fake.raw_set(f"{old}/log/d1/e1", {"type": "review", "r": 3})
    fake.raw_set(f"{old}/log/d1/e2", {"type": "review", "r": 1})
    fake.raw_set(f"{old}/prefs", {"current_subject": "car"})
    fake.raw_set(f"{old}/feedback/f1", {"text": "bug"})
    fake.raw_set(f"{old}/sessions/20261012-170448-5b71/user", {"archived": True})
    fake.raw_set(f"{old}/sessions/bad-sid/user", {"archived": True})
    fake.raw_set(f"{old}/sessions/20261012-170448-5b72/msgs/m0001", {"text": "x"})
    fake.raw_set(f"{old}/requests/r1/req", {"kind": "message"})
    # Already in the new root (a newer write): kept, never clobbered.
    fake.set(f"{e2e.ROOT}/log/d1/e2", {"type": "review", "r": 4})

    async def go() -> None:
        db = fake.rtdb()
        assert await e2e.migrate(db) == 4
        assert await e2e.migrate(db) == 0  # one-time
        await db.aclose()

    asyncio.run(go())
    assert fake.get(f"{e2e.ROOT}/log/d1") == {
        "e1": {"type": "review", "r": 3},
        "e2": {"type": "review", "r": 4},
    }
    assert fake.get(f"{e2e.ROOT}/prefs/current_subject") == "car"
    assert fake.get(f"{e2e.ROOT}/feedback/f1") == {"text": "bug"}
    assert fake.get(f"{e2e.ROOT}/sessions") == {
        "20261012-170448-5b71": {"user": {"archived": True}}
    }
    assert fake.get(f"{e2e.ROOT}/requests") is None
    assert fake.get(f"{e2e.ROOT}/migration/v1_copied_at") == fake.now_ms
    assert fake.raw_get(f"{old}/meta/min_client") == e2e.MIN_CLIENT
    assert fake.raw_get(f"{old}/log/d1/e1") == {"type": "review", "r": 3}  # kept
    assert "bug" not in json.dumps(fake.raw_get(e2e.ROOT))


def test_relay_startup_unlocks_and_stays_closed_while_locked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    eng, _ = engine(tmp_path)
    fake = FakeRtdb(sealed=False)
    secrets = iter(["", "pw"])
    slept: list[float] = []

    async def no_sleep(delay: float) -> None:
        slept.append(delay)

    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    monkeypatch.setattr(e2e, "unlock", _fast_unlock(e2e.unlock))

    async def go() -> None:
        relay = worker.Relay(
            eng, fake.rtdb(), PhaseSink(), eng.time, lambda: next(secrets)
        )
        await relay._startup()
        assert slept  # locked first: retried, nothing written meanwhile
        assert relay.w.rtdb.sealer is not None
        await relay.w.rtdb.aclose()

    asyncio.run(go())
    assert fake.raw_get(f"{e2e.ROOT}/meta")["min_client"] == e2e.MIN_CLIENT
    assert '"subject"' not in json.dumps(fake.raw_get(f"{e2e.ROOT}/live"))


def test_header_vector_unlocks_and_opens_for_flutter_parity() -> None:
    header = VECTORS["header"]
    fake = FakeRtdb(sealed=False)
    fake.raw_set(header["path"], header["text"])

    async def go() -> e2e.Sealer:
        db = fake.rtdb()
        key = await e2e.unlock(db, header["passphrase"])
        await db.aclose()
        return e2e.Sealer(key.cipher())

    unit = header["unit"]
    assert asyncio.run(go()).open(unit["path"], unit["stored"]) == unit["value"]


def test_header_store_protocol_extras() -> None:
    fake = FakeRtdb(sealed=False)

    async def go() -> None:
        db = fake.rtdb()
        store = e2e._HeaderStore(db, asyncio.get_running_loop())
        assert store.list_directory("tutor") == []
        assert store.can_access_remote()
        with pytest.raises(NotImplementedError):
            store.delete_file("tutor/e2e")
        await db.aclose()

    asyncio.run(go())


def test_passphrase_reads_the_password_under_the_redirected_home() -> None:
    # Imported at collection, before the conftest guard; HOME is tmp here.
    assert unpatched_passphrase() == ""
    config.password_file().parent.mkdir(parents=True)
    config.password_file().write_text("pw\n")
    assert unpatched_passphrase() == "pw"


def test_an_unreadable_password_file_keeps_the_key_locked(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    pw = tmp_path / "password"
    pw.write_text("pw")
    pw.chmod(0)
    assert config.read_passphrase(pw) == ""
    assert "e2e stays locked" in caplog.text


def test_relay_reads_the_passphrase_late(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "passphrase", lambda: "late")
    assert worker.Relay._passphrase() == "late"
