# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The paired-phone store and the public gate's environment (DOCS-public.md)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from tutor.device_gate import DeviceStore, PublicGate

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_store_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "d.json"
    store = DeviceStore(path)
    assert not store.check("t")  # missing file
    path.write_text("not json", encoding="utf-8")
    assert not store.check("t")
    path.write_text('{"a": 1}', encoding="utf-8")
    assert not store.check("t")
    path.write_text('[1, {"sha256": 5}, {"sha256": "x"}]', encoding="utf-8")
    assert not store.check("t")
    store.add("t", "x" * 200)  # junk rows stay inert
    assert store.check("t")
    assert not store.check("u")
    assert len(json.loads(path.read_text(encoding="utf-8"))[-1]["ua"]) == 80
    store.add("v", None)
    assert store.check("t")
    assert store.check("v")


def test_from_env_reads_paths_and_the_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TUTOR_DEVICES", str(tmp_path / "dev.json"))
    monkeypatch.setenv("TUTOR_PUBLIC_HOST", "Phone.Example")
    built = PublicGate.from_env()
    assert built is not None
    assert built.host == "phone.example"
    built.store.add("t", None)
    assert (tmp_path / "dev.json").is_file()
    monkeypatch.setenv("TUTOR_PUBLIC_HOST", "")
    assert PublicGate.from_env() is None
    monkeypatch.delenv("TUTOR_PUBLIC_HOST")
    default = PublicGate.from_env()
    assert default is not None
    assert default.host == "tutor.kuhy.duckdns.org"
