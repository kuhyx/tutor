# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``python -m tutor migrate [--data DIR]``: the PLC deck becomes a subject.

``DOCS-contract.md`` §11, idempotent (a second run changes nothing):

- ``subjects/automation/deck/*.json`` -> subject ``automation`` (plan rev 1,
  approved; one ``ready`` module per ``cards.TOPICS`` entry, keeping its id
  prefixes; a module requires the EARLIER topics its cards' ``requires`` reach into;
  cards ``origin:"seed"``, rev 1). An existing subject is left alone, so card
  edits made since survive.
- ``progress.json`` ``cards_done`` -> one ``taught`` event per card (``at`` =
  the recorded time, its session), unless the log already has one; event ids
  are derived from the card, so a rerun writes the same ids.
- ``mastered`` -> ``concepts.json`` (names not there yet).
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import logging
from pathlib import Path
import time
from typing import Any, Final

from tutor import cards
from tutor.curriculum import card_rules, profiles
from tutor.curriculum.eventlog import EventLog
from tutor.curriculum.fold import fold
from tutor.curriculum.ids import device_id, ulid
from tutor.curriculum.records import CardRec, Meta, Module, Plan
from tutor.curriculum.subject_store import Change, SubjectStore
from tutor.store import Store, data_dir

_logger = logging.getLogger(__name__)
DECK_DIR: Final = Path(__file__).resolve().parents[2] / "subjects/automation/deck"
SUBJECT: Final = "automation"
TITLE: Final = "Industrial automation"
GOAL: Final = (
    "Understand industrial automation: PLCs, relays, field devices, "
    "protocols and OT security"
)


def _ms(iso: object, fallback: int) -> int:
    try:
        return int(datetime.fromisoformat(str(iso)).timestamp() * 1000)
    except ValueError:
        _logger.warning("no usable time %r; using the migration time", iso)
        return fallback


def seed(deck: list[cards.Card], now: int) -> tuple[Plan, dict[str, CardRec]]:
    """The automation plan and cards from the deck."""
    module_of = {c.id: c.topic.stem.replace("_", "-") for c in deck}
    modules: list[Module] = []
    found: dict[str, CardRec] = {}
    for topic in cards.TOPICS:
        mid = topic.stem.replace("_", "-")
        own = [c for c in deck if c.topic.stem == topic.stem]
        needs = {module_of[r] for c in own for r in c.requires} - {mid}
        # Only earlier topics: fundamentals stays the root even though one of
        # its cards needs later language cards (card-level gating keeps that).
        order = [m.id for m in modules if m.id in needs]
        modules.append(
            Module(mid, topic.title, "", order, 1, list(topic.prefixes), "ready")
        )
        modules[-1].cards = len(own)
        for i, card in enumerate(own, 1):
            found[card.id] = CardRec(
                module=mid,
                order=i,
                front=card.front,
                back=card.back,
                source=card.source,
                excerpt=card.excerpt,
                requires=list(card.requires),
                origin="seed",
                created=now,
            )
    notes = "Migrated from the PLC deck: one module per deck topic, in deck order."
    return Plan(1, "approved", notes, modules), found


def _taught(root: Path, progress: dict[str, Any], ids: set[str], now: int) -> int:
    """Append a ``taught`` event per done card the log lacks; returns how many."""
    log = EventLog(root)
    have = {
        c
        for (s, c), f in fold(log.read()).cards.items()
        if s == SUBJECT and (f.taught or f.new_at)
    }
    dev = device_id(root / "device_id")
    events = []
    for cid, info in progress.get("cards_done", {}).items():
        if cid not in ids or cid in have or not isinstance(info, dict):
            continue
        at = _ms(info.get("at"), now)
        entropy = hashlib.sha256(f"migrate:{cid}".encode()).digest()
        event = {
            "dev": dev,
            "eid": ulid(at, entropy),
            "k": "taught",
            "s": SUBJECT,
            "c": cid,
            "at": at,
        }
        if isinstance(info.get("session"), str):
            event["session"] = info["session"]
        events.append(event)
    return len(log.append(events))


def _concepts(
    store: SubjectStore, meta: Meta, progress: dict[str, Any], now: int
) -> list[dict[str, Any]]:
    """Append ``mastered`` names missing from ``concepts.json``; returns them."""
    concepts = store.concepts(SUBJECT)
    names = {c.get("name") for c in concepts}
    fresh = [
        {
            "name": name,
            "at": _ms(info.get("at"), now),
            "card": info.get("card", ""),
            "session": info.get("session", ""),
        }
        for name, info in progress.get("mastered", {}).items()
        if name not in names and isinstance(info, dict)
    ]
    if fresh:
        store.commit(SUBJECT, meta, Change(concepts=[*concepts, *fresh]))
    return fresh


def migrate(
    root: Path, deck_dir: Path = DECK_DIR, now: int | None = None
) -> dict[str, Any]:
    """Run the migration on data dir ``root``; returns the counts."""
    now = now or int(time.time() * 1000)
    deck = cards.load_deck(deck_dir)
    store = SubjectStore(root)
    progress = Store(root).progress()
    meta = store.meta(SUBJECT)
    created = meta is None
    if meta is None:
        plan, found = seed(deck, now)
        card_rules.check_set(found, {m.id: m for m in plan.modules})
        meta = Meta(TITLE, GOAL, "active", now, origin="seed")
        profile = profiles.automation().to_json()
        store.commit(
            SUBJECT, meta, Change(plan=plan, cards=found, concepts=[], profile=profile)
        )
    fresh = _concepts(store, meta, progress, now)
    taught = _taught(root, progress, {c.id for c in deck}, now)
    stored = store.plan(SUBJECT)
    return {
        "subject": "created" if created else "kept",
        "modules": len(stored.modules) if stored else 0,
        "cards": len(store.cards(SUBJECT)),
        "taught_added": taught,
        "taught_total": len(fold(EventLog(root).read()).taught_ids(SUBJECT)),
        "concepts_added": len(fresh),
        "concepts_total": len(store.concepts(SUBJECT)),
    }


def main(argv: list[str]) -> int:
    """CLI: migrate the data dir (default ``$TUTOR_DATA``) and print counts."""
    parser = argparse.ArgumentParser(
        prog="python -m tutor migrate", description=__doc__
    )
    parser.add_argument("--data", type=Path, default=None, help="data dir")
    args = parser.parse_args(argv)
    counts = migrate(args.data or data_dir())
    print(json.dumps(counts, indent=1))
    return 0
