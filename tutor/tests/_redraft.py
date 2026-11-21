# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Redraft test support: a subject with history and a model that plays Fable."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from tutor.curriculum import draft_prompt, judge, paths, quality_judge
from tutor.curriculum.redraft import prompts
from tutor.tests._cur import T0, card, make_ctx, module, review, subject, taught

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.curriculum.context import Context
    from tutor.tests._cur import Fakes

URL = "https://example.org/engine"
TEXT = "the piston turns the crank shaft round and round " * 60


def draft(cid: str, front: str = "", **over: Any) -> dict[str, Any]:
    """One drafted card."""
    base = {
        "id": cid,
        "front": front or f"What does the {cid} do?",
        "back": "It turns the crank.",
        "mnemonic": "",
        "source": 1,
        "excerpt": "the piston turns the crank shaft round and round",
        "requires": [],
    }
    return {**base, **over}


@dataclass
class Fable:
    """Answers each redraft call by its system prompt; counts the calls."""

    cards: list[dict[str, Any]]
    pairs: list[tuple[str, str]] = field(default_factory=list)
    pieces: list[dict[str, Any]] = field(default_factory=list)
    off_topic: set[str] = field(default_factory=set)
    repairs: list[dict[str, Any]] = field(default_factory=list)
    seen: list[str] = field(default_factory=list)
    prompts: dict[str, str] = field(default_factory=dict)
    fail: Exception | None = None

    def __call__(
        self, system: str, prompt: str, schema: dict[str, Any]
    ) -> dict[str, Any]:
        kind = self._kind(system)
        self.seen.append(kind)
        self.prompts[kind] = prompt
        if self.fail is not None:
            raise self.fail
        if kind == "draft":
            return {"cards": self.cards}
        if kind == "repair":
            return {"cards": self.repairs}
        if kind in {"judge", "audit", "gate"}:
            return self._verdicts(kind, schema)
        if kind == "match":
            return {"pairs": [{"new": n, "old": o} for n, o in self.pairs]}
        return self._rest(kind)

    def _verdicts(self, kind: str, schema: dict[str, Any]) -> dict[str, Any]:
        props = schema["properties"]["verdicts"]["items"]["properties"]
        if kind != "gate":
            ids = props["id"]["enum"]
            return {"verdicts": [{"id": i, "broken": [], "why": ""} for i in ids]}
        return {
            "verdicts": [
                {
                    "id": c["id"],
                    "on_topic": c["id"] not in self.off_topic,
                    "module": props["module"]["enum"][0],
                    "repeats": "",
                    "reason": "",
                }
                for c in self.cards
            ]
        }

    def _rest(self, kind: str) -> dict[str, Any]:
        if kind == "split":
            return {"pieces": self.pieces}
        ids = [c["id"] for c in self.cards]
        return {
            "paths": [
                {
                    "id": i,
                    "opening": f"What do you know about {i}?",
                    "probes": [],
                    "misconception": "",
                    "correction": "",
                    "hints": [],
                    "tell": [],
                    "pass_criterion": "Says what it does.",
                    "typed_follow_up": False,
                }
                for i in ids
                if f'"id": "{i}"' in self.prompts["paths"]
            ]
        }

    @staticmethod
    def _kind(system: str) -> str:
        if system.startswith(draft_prompt.system(12)[:60]):
            return "draft"
        named = {
            judge.GATE_SYSTEM: "gate",
            prompts.MATCH_SYSTEM: "match",
            prompts.SPLIT_SYSTEM: "split",
            paths.SYSTEM: "paths",
            quality_judge.REPAIR_SYSTEM: "repair",
        }
        if system in named:
            return named[system]
        return "audit" if system.startswith("This is the FINAL AUDIT") else "judge"


def car(tmp_path: Path, n: int = 3, **mod: Any) -> tuple[Context, Fakes]:
    """Subject ``car``: module ``a`` (``n`` cards, ``old-0`` taught), ``b``, ``c``."""
    ctx, fakes = make_ctx(tmp_path)
    fakes.texts[URL] = TEXT
    mods = [
        module("a", status=mod.pop("status", "ready"), **mod),
        module("b", "a"),
        module("c", "b"),
    ]
    found = {f"old-{i}": card("a", i + 1, source=URL) for i in range(n)}
    subject(ctx, modules=mods, found=found)
    taught(ctx, "car", "old-0", T0)
    review(ctx, "car", "old-0", T0 + 1000, 3)
    return ctx, fakes
