# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""F33 seeder test support: the scripts as `up` imports them, a sandbox, ``car``."""

from __future__ import annotations

import importlib
from pathlib import Path
import sys
from typing import TYPE_CHECKING, Any

from tutor.tests._cur import T0, D, card, make_ctx, module, subject, taught

if TYPE_CHECKING:
    import pytest

    from tutor.curriculum.context import Context

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
NOW = T0 + 30 * D
MIN = 60_000


def load(monkeypatch: pytest.MonkeyPatch) -> tuple[Any, Any]:
    """``e2e_fallback_seed`` and ``e2e_fallback_state``, imported fresh from scripts/."""
    monkeypatch.syspath_prepend(str(SCRIPTS))
    for name in ("e2e_seed", "e2e_fallback_state", "e2e_fallback_seed"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    return (
        importlib.import_module("e2e_fallback_seed"),
        importlib.import_module("e2e_fallback_state"),
    )


def sandbox(tmp_path: Path) -> Path:
    """A sandbox data dir whose worker is ``dev-pc`` (``make_ctx``'s device)."""
    root = tmp_path / "sandbox" / "data"
    root.mkdir(parents=True)
    (root / "device_id").write_text("dev-pc\n")
    return root


def car(data: Path, n: int = 4, **marks: int) -> Context:
    """``car``: ready module a (a1..an), locked b (b1, b2); ``marks``: taught at."""
    ctx, _ = make_ctx(data)
    found = {f"a{i}": card("a", i) for i in range(1, n + 1)}
    found |= {"b1": card("b", 1), "b2": card("b", 2)}
    subject(ctx, modules=[module("a", status="ready"), module("b", "a")], found=found)
    subject(
        ctx, "zed", modules=[module("z", status="ready")], found={"z1": card("z", 1)}
    )
    taught(ctx, "zed", "z1", T0, 9)  # due long before NOW
    for i, (cid, at) in enumerate(sorted(marks.items())):
        taught(ctx, "car", cid, at, i + 1)
    return ctx
