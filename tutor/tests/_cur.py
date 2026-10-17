# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Curriculum test support: a context with a scripted model, web and check."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from tutor import sources
from tutor.curriculum.context import Context
from tutor.curriculum.records import CardRec, Meta, Module, Plan
from tutor.curriculum.subject_store import Change

if TYPE_CHECKING:
    from pathlib import Path

T0 = 1_800_000_000_000
H = 3_600_000
D = 24 * H


@dataclass
class Fakes:
    """What the fakes saw and will answer."""

    replies: list[Any] = field(default_factory=list)
    prompts: list[tuple[str, str]] = field(default_factory=list)
    pages: dict[str, bytes] = field(default_factory=dict)
    bad_excerpts: set[str] = field(default_factory=set)
    texts: dict[str, str] = field(default_factory=dict)
    now: list[int] = field(default_factory=lambda: [T0])

    def model(self, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        del schema
        self.prompts.append((system, prompt))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return dict(reply)

    def fetch(self, url: str) -> bytes:
        if url not in self.pages:
            msg = f"no route to {url}"
            raise OSError(msg)
        return self.pages[url]

    def check(self, cid: str, url: str, excerpt: str) -> sources.Mismatch | None:
        if excerpt in self.bad_excerpts:
            return sources.Mismatch(cid, url, "excerpt not found in the page text")
        return None

    def text(self, url: str) -> str:
        if url not in self.texts:
            msg = f"no text for {url}"
            raise OSError(msg)
        return self.texts[url]

    def clock(self) -> int:
        return self.now[0]


def make_ctx(root: Path, fakes: Fakes | None = None) -> tuple[Context, Fakes]:
    """A context on ``root`` with every outside call faked."""
    fakes = fakes or Fakes()
    ctx = Context(
        root,
        clock=fakes.clock,
        model=fakes.model,
        fetch=fakes.fetch,
        check=fakes.check,
        text=fakes.text,
        device="dev-pc",
    )
    return ctx, fakes


def module(mid: str, *requires: str, status: str = "locked", **kw: Any) -> Module:
    """A module."""
    return Module(
        mid, mid.replace("-", " ").title(), "", list(requires), status=status, **kw
    )


def card(mod: str, order: int, *requires: str, **kw: Any) -> CardRec:
    """A valid card of ``mod``."""
    base: dict[str, Any] = {
        "front": f"What is thing {order} of {mod}?",
        "back": "It is a thing.",
        "source": "https://en.wikipedia.org/wiki/Thing",
        "excerpt": "a thing is an object that one need not name",
    }
    base.update(kw)
    return CardRec(module=mod, order=order, requires=list(requires), **base)


def subject(
    ctx: Context,
    name: str = "car",
    modules: list[Module] | None = None,
    found: dict[str, CardRec] | None = None,
    **meta_kw: Any,
) -> Plan:
    """Write an approved, active subject; returns its plan."""
    mods = modules or [module("a", status="ready"), module("b", "a"), module("c", "b")]
    plan = Plan(1, meta_kw.pop("plan_status", "approved"), "notes", mods)
    status = meta_kw.pop("status", "active")
    meta = Meta("Cars", "learn cars", status, T0, **meta_kw)
    ctx.subjects.commit(name, meta, Change(plan=plan, cards=found or {}, concepts=[]))
    return plan


def taught(ctx: Context, subj: str, cid: str, at: int, eid_n: int = 0) -> None:
    """Append a taught event, by the worker (``ctx.device``) as in real logs."""
    from tutor.curriculum.ids import ulid

    ctx.log.append(
        [
            {
                "dev": ctx.device,
                "eid": ulid(at, bytes([eid_n] * 10)),
                "k": "taught",
                "s": subj,
                "c": cid,
                "at": at,
            }
        ]
    )


def review(
    ctx: Context,
    subj: str,
    cid: str,
    at: int,
    r: int,
    *,
    dev: str = "d1",
    src: str | None = None,
) -> None:
    """Append a review event (by a phone ``d1``; ``src="drill"``: a drill pick)."""
    from tutor.curriculum.ids import ulid

    ctx.log.append(
        [
            {
                "dev": dev,
                "eid": ulid(at, bytes([r, 7] * 5)),
                "k": "review",
                "s": subj,
                "c": cid,
                "at": at,
                "r": r,
                "rev": 1,
                **({"src": src} if src else {}),
            }
        ]
    )
