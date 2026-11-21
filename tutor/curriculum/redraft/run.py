# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""A backfill run on disk: the snapshot, the units and their states.

``$TUTOR_DATA/redraft/``: ``run.json`` (the units, in order), ``before/``
(each subject's ``meta``/``plan``/``cards`` as they were, plus ``history``:
what the event log says about its cards), ``replies/`` (the model reply
cache), ``out/`` (each built unit). Units are built from ``before/`` only,
so their prompts never depend on the order other units finish in.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import shutil
import threading
import time
from typing import TYPE_CHECKING, Any, Final

from tutor.curriculum.errors import BAD_REQUEST, RequestError
from tutor.curriculum.fold import fold
from tutor.curriculum.records import CardRec, Meta, Plan
from tutor.curriculum.subject_store import read_json, write_json

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.curriculum.context import Context
    from tutor.curriculum.fold import CardFold

PENDING: Final = "pending"
DONE: Final = "done"
FAILED: Final = "failed"
AGAIN: Final = 1  # the FSRS rating of a failed review
MAX_TRIES: Final = 3
_PARTS: Final = ("meta", "plan", "cards")
_STATE: Final = threading.Lock()  # run.json read-modify-write


@dataclass
class Unit:
    """One module to redraft."""

    subject: str
    module: str
    state: str = PENDING
    tries: int = 0
    error: str = ""
    keys: list[str] = field(default_factory=list)  # reply-cache keys it used

    @property
    def name(self) -> str:
        """``subject/module``."""
        return f"{self.subject}/{self.module}"


@dataclass(frozen=True)
class Before:
    """One subject as it was when the run started."""

    subject: str
    meta: Meta
    plan: Plan
    cards: dict[str, CardRec]
    history: dict[str, Any]

    def live(self, module_id: str) -> dict[str, CardRec]:
        """The module's cards that were live, in order."""
        found = {
            cid: c
            for cid, c in self.cards.items()
            if c.module == module_id and not c.suspended
        }
        return dict(sorted(found.items(), key=lambda item: item[1].order))

    @property
    def taught(self) -> set[str]:
        """Ids of the cards the learner had been taught."""
        return set(self.history.get("taught", []))

    @property
    def hard(self) -> set[str]:
        """Ids flagged hard or failed in a review (rule ``mnemonic``)."""
        return set(self.history.get("hard", []))

    @property
    def flags(self) -> dict[str, list[str]]:
        """Card id -> the reasons of the flags on its current rev."""
        found = self.history.get("flags", {})
        return found if isinstance(found, dict) else {}


def root(ctx: Context) -> Path:
    """The run's directory."""
    return ctx.data_dir / "redraft"


def _is_hard(state: CardFold, reasons: list[str]) -> bool:
    failed = any(rating == AGAIN for _, rating in state.reviews)
    return failed or any("hard" in r.casefold() for r in reasons)


def history(ctx: Context, subject: str, cards: dict[str, CardRec]) -> dict[str, Any]:
    """What the log says about ``subject``'s cards (archived or not)."""
    events = ctx.log.read()
    folded = fold(events)
    flags: dict[str, list[str]] = {}
    for event in events:
        card = cards.get(str(event.get("c")))
        if event["k"] != "flag" or event.get("s") != subject or card is None:
            continue
        if event.get("rev") == card.rev:
            flags.setdefault(event["c"], []).append(str(event.get("reason", "")))
    hard = [
        cid for cid in cards if _is_hard(folded.card(subject, cid), flags.get(cid, []))
    ]
    taught = sorted(folded.taught_ids(subject) & set(cards))
    return {"flags": flags, "hard": hard, "taught": taught}


def units(ctx: Context) -> list[Unit]:
    """The run's units (``bad_request`` when no run was started)."""
    raw = read_json(root(ctx) / "run.json", None)
    if not isinstance(raw, dict) or not isinstance(raw.get("units"), list):
        msg = f"no redraft run in {ctx.data_dir}; run `redraft start` first"
        raise RequestError(BAD_REQUEST, msg)
    return [Unit(**u) for u in raw["units"]]


def exists(ctx: Context) -> bool:
    """Whether a run was started in this data dir."""
    return (root(ctx) / "run.json").is_file()


def pending(ctx: Context) -> list[Unit]:
    """The units still to build ([] when there is no run)."""
    return [u for u in units(ctx) if u.state == PENDING] if exists(ctx) else []


def save(ctx: Context, found: list[Unit], started: int | None = None) -> None:
    """Write ``run.json`` (``started``: only when the run is created)."""
    where = root(ctx) / "run.json"
    old = read_json(where, {})
    was = old.get("started") if isinstance(old, dict) else None
    at = started if started is not None else was
    write_json(where, {"started": at, "units": [asdict(u) for u in found]})


def update(ctx: Context, unit: Unit) -> None:
    """Store one unit's new state (other units as they are on disk)."""
    with _STATE:
        found = units(ctx)
        found = [unit if u.name == unit.name else u for u in found]
        save(ctx, found)


def before(ctx: Context, subject: str) -> Before:
    """The subject's snapshot."""
    where = root(ctx) / "before" / subject
    meta, plan, cards = (read_json(where / f"{p}.json", None) for p in _PARTS)
    if not (isinstance(meta, dict) and isinstance(plan, dict)):
        msg = f"no snapshot of {subject}"
        raise RequestError(BAD_REQUEST, msg)
    found = {
        cid: CardRec.from_json(c)
        for cid, c in (cards if isinstance(cards, dict) else {}).items()
    }
    past = read_json(where / "history.json", {})
    return Before(
        subject,
        Meta.from_json(meta),
        Plan.from_json(plan),
        found,
        past if isinstance(past, dict) else {},
    )


def backup(ctx: Context, now_s: float | None = None) -> Path:
    """Copy ``subjects/`` to ``backups/subjects-<timestamp>/``; returns it."""
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now_s))
    target = ctx.data_dir / "backups" / f"subjects-{stamp}"
    n = 1
    while target.exists():  # a second run started within the same second
        n += 1
        target = target.with_name(f"subjects-{stamp}-{n}")
    shutil.copytree(ctx.subjects.base, target)
    return target


def start(
    ctx: Context, replies: Path | None = None, only: frozenset[str] = frozenset()
) -> list[Unit]:
    """Back up, snapshot every subject and queue a unit per module with cards.

    ``replies``: another run's reply cache to replay (a dry run's);
    ``only``: queue just these ``subject/module`` units (a trial). A run
    with pending units is never replaced (``bad_request``).
    """
    if pending(ctx):
        msg = "a redraft run is still pending here; let it finish first"
        raise RequestError(BAD_REQUEST, msg)
    here = root(ctx)
    backup(ctx)
    for part in ("before", "out"):
        shutil.rmtree(here / part, ignore_errors=True)
    if replies is not None and replies.is_dir():
        shutil.copytree(replies, here / "replies", dirs_exist_ok=True)
    found: list[Unit] = []
    for subject in ctx.subjects.subjects(archived=True):
        plan = ctx.subjects.plan(subject)
        if plan is None or plan.status != "approved":
            continue
        where, snap = ctx.subjects.dir(subject), here / "before" / subject
        snap.mkdir(parents=True)
        for part in _PARTS:
            shutil.copy2(where / f"{part}.json", snap / f"{part}.json")
        cards = ctx.subjects.cards(subject)
        write_json(snap / "history.json", history(ctx, subject, cards))
        live = {c.module for c in cards.values() if not c.suspended}
        found += [Unit(subject, m.id) for m in plan.modules if m.id in live]
    found = [u for u in found if not only or u.name in only]
    save(ctx, found, started=ctx.clock())
    return found
