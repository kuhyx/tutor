# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""scripts/e2e_prepare.py: the agent-E2E sandbox copy never carries live state."""

from __future__ import annotations

from datetime import datetime
import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

LIVE = "64048915-0c43-44c0-aa10-937999a5212f"
SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "e2e_prepare.py"


def _module() -> Any:
    """Load the script fresh (its REAL_DATA follows the moved HOME)."""
    spec = importlib.util.spec_from_file_location("e2e_prepare", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ms(stamp: str) -> int:
    return int(
        datetime.strptime(stamp, "%Y-%m-%d %H:%M").astimezone().timestamp() * 1000
    )


@pytest.fixture
def src(tmp_path: Path) -> Path:
    root = tmp_path / "live"
    (root / "sessions").mkdir(parents=True)
    (root / "device_id").write_text(f"{LIVE}\n")
    for name in ("ledger.json", "ledger.lock", "server.log"):
        (root / name).write_text("{}")
    (root / "sandbox").mkdir()
    events = [
        {
            "dev": LIVE,
            "eid": "01A",
            "k": "taught",
            "s": "x",
            "c": "a",
            "at": _ms("2026-10-17 18:00"),
        },
        {
            "dev": LIVE,
            "eid": "01B",
            "k": "taught",
            "s": "x",
            "c": "b",
            "at": _ms("2026-10-17 22:10"),
        },
    ]
    (root / "log.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
    (root / "sessions/20261017-180000-aaaa.jsonl").write_text(f'{{"by": "{LIVE}"}}\n')
    (root / "sessions/20261017-220814-bbbb.jsonl").write_text("{}\n")
    return root


def test_copy_drops_the_ledger_and_replaces_the_device_id(
    src: Path, tmp_path: Path
) -> None:
    dst = tmp_path / "box"
    new = _module().prepare(src, dst)
    assert new != LIVE
    assert (dst / "device_id").read_text().strip() == new
    for name in ("ledger.json", "ledger.lock", "server.log", "sandbox"):
        assert not (dst / name).exists()
    assert all(LIVE not in p.read_text() for p in dst.rglob("*") if p.is_file())
    assert (src / "device_id").read_text().strip() == LIVE


def test_as_of_rewinds_the_log_and_the_transcripts(src: Path, tmp_path: Path) -> None:
    dst = tmp_path / "box"
    as_of = datetime.strptime("2026-10-17 22:00", "%Y-%m-%d %H:%M").astimezone()
    _module().prepare(src, dst, new_cap=10, as_of=as_of)
    events = [json.loads(line) for line in (dst / "log.jsonl").read_text().splitlines()]
    assert [e.get("c") for e in events] == ["a", None]
    assert events[-1]["k"] == "new_cap"
    assert events[-1]["n"] == 10
    assert sorted(p.name for p in (dst / "sessions").iterdir()) == [
        "20261017-180000-aaaa.jsonl"
    ]


def test_refuses_the_real_data_dir_and_a_used_dst(
    src: Path, tutor_sandbox: Path, tmp_path: Path
) -> None:
    module = _module()
    with pytest.raises(module.PrepareError):
        module.prepare(src, tutor_sandbox / "home/.local/share/tutor/box")
    with pytest.raises(module.PrepareError):
        module.prepare(src, src / "box")
    used = tmp_path / "used"
    used.mkdir()
    (used / "x").write_text("")
    with pytest.raises(module.PrepareError):
        module.prepare(src, used)


def test_as_of_cuts_a_kept_transcript_mid_session(src: Path, tmp_path: Path) -> None:
    """A session at card end, before its Next card: F3's starting point."""
    kept = src / "sessions/20261017-180000-aaaa.jsonl"

    def at(clock: str) -> str:
        shape = "%Y-%m-%d %H:%M:%S"
        return datetime.strptime(f"2026-10-17 {clock}", shape).astimezone().isoformat()

    events = [
        {"type": "start", "logged_at": at("18:00:00")},
        {"type": "tutor", "logged_at": at("18:05:10")},
        {"type": "next_card", "logged_at": at("18:05:50")},
        {"type": "stop", "logged_at": at("18:05:50")},
    ]
    kept.write_text("".join(json.dumps(e) + "\n" for e in events))
    module = _module()
    as_of = module.parse_as_of("2026-10-17 18:05:30")
    module.prepare(src, tmp_path / "box", as_of=as_of)
    cut = (tmp_path / "box/sessions/20261017-180000-aaaa.jsonl").read_text()
    assert [json.loads(x)["type"] for x in cut.splitlines()] == ["start", "tutor"]
    minute = datetime.strptime("2026-10-17 18:05", "%Y-%m-%d %H:%M").astimezone()
    assert module.parse_as_of("2026-10-17 18:05") == minute
