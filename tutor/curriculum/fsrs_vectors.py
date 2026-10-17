# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Golden vectors for the fold + FSRS: ``contract/fsrs_vectors.json``.

The Dart fold (a port of py-fsrs 6.3.2's Scheduler) must reproduce every
case: per card ``taught``, ``due`` (ms, exact), ``stability`` and
``difficulty`` (1e-6), ``state``, ``flagged``, ``good`` and ``reviewed``
(§6: a drill pick never counts, ``fold.is_drill``), plus which
review eids the fold ``dropped`` (cross-device duplicates), ``ignored``
(card untaught) or found ``undone`` (named by a ``review_undo`` ``of``).
Regenerate with ``python -m tutor.curriculum.fsrs_vectors``;
a test fails when the file and this generator disagree.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Final

from tutor.curriculum.fold import fold
from tutor.curriculum.fsrs_cases import CASES, T0, Spec
from tutor.curriculum.ids import ulid
from tutor.curriculum.rules import good, reviewed

OUT: Final = Path(
    os.environ.get("TUTOR_VECTORS_OUT")
    or Path(__file__).resolve().parents[2] / "contract" / "fsrs_vectors.json"
)


def _events(name: str, spec: Spec) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, (kind, card, offset, dev, raw_extra) in enumerate(spec[0]):
        seed = hashlib.sha256(f"{name}/{i}".encode()).digest()
        at = T0 + offset
        extra = dict(raw_extra)
        if isinstance(extra.get("of"), int):  # an earlier event of the case
            extra["of"] = out[extra["of"]]["eid"]
        out.append(
            {
                "dev": dev,
                "eid": ulid(at, seed),
                "k": kind,
                "s": "car",
                "c": card,
                "at": at,
                **({"rev": 1} if kind == "review" else {}),
                **extra,
            }
        )
    return out


def case(name: str, spec: Spec) -> dict[str, Any]:
    """One vector: its events, card revs and the fold's expected result."""
    events = _events(name, spec)
    folded = fold(events)
    expect = {}
    for card, rev in spec[1].items():
        state = folded.card("car", card)
        memory = state.fsrs_state() or {}
        expect[card] = {
            "taught": state.taught,
            "due": memory.get("due"),
            "stability": memory.get("stability"),
            "difficulty": memory.get("difficulty"),
            "state": memory.get("state"),
            "flagged": state.flagged(rev),
            "good": good(state),
            "reviewed": reviewed(state),
        }
    return {
        "name": name,
        "events": list(reversed(events)),  # unsorted on purpose: the fold sorts
        "cards": {card: {"rev": rev} for card, rev in spec[1].items()},
        "expect": expect,
        "dropped": folded.dropped,
        "ignored": folded.ignored,
        "undone": folded.undone,
    }


def build() -> list[dict[str, Any]]:
    """Every case."""
    return [case(name, spec) for name, spec in CASES.items()]


def render() -> str:
    """The file's text."""
    return json.dumps(build(), indent=1) + "\n"


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(), encoding="utf-8")
    sys.stdout.write(f"wrote {len(CASES)} cases to {OUT}\n")
