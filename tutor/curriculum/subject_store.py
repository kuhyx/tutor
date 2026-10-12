# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The PC's canonical subject files under ``$TUTOR_DATA/subjects/<subj>/``.

``meta.json``, ``plan.json``, ``cards.json`` (id -> card), ``concepts.json``
and ``profile.json``; shapes as ``DOCS-contract-curriculum.md``. Every write
is a temp file + rename, and every :meth:`SubjectStore.commit` bumps
``meta.rev`` once, written last, so the relay worker re-publishes a subject
whenever its local ``rev`` is ahead of the RTDB copy. One process-wide lock
serialises read-modify-write between the chat lane, the build lane and the
fold.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import threading
from typing import TYPE_CHECKING, Any, Final

from tutor.curriculum.errors import BAD_REQUEST, RequestError
from tutor.curriculum.ids import valid_id
from tutor.curriculum.records import CardRec, Meta, Plan, plan_json

if TYPE_CHECKING:
    from pathlib import Path

LOCK: Final = threading.RLock()


@dataclass
class Change:
    """The parts of a subject one commit writes (None: unchanged)."""

    plan: Plan | None = None
    cards: dict[str, CardRec] | None = None
    concepts: list[dict[str, Any]] | None = None
    profile: dict[str, Any] | None = None


def write_json(path: Path, data: object) -> None:
    """Write ``data`` to ``path`` atomically (temp file, then rename)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", "utf-8")
    tmp.replace(path)


def read_json(path: Path, default: object) -> object:
    """``path`` parsed, or ``default`` when it does not exist."""
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


class SubjectStore:
    """Read and write the subjects of one data dir."""

    def __init__(self, root: Path) -> None:
        """``root`` is the data dir (``$TUTOR_DATA``)."""
        self.root = root
        self.base = root / "subjects"

    def dir(self, subject: str) -> Path:
        """The subject's directory; a bad id never becomes a path."""
        if not valid_id(subject):
            msg = f"bad subject id {subject!r}"
            raise RequestError(BAD_REQUEST, msg)
        return self.base / subject

    def subjects(self) -> list[str]:
        """Every subject with a ``meta.json``, sorted."""
        if not self.base.is_dir():
            return []
        return sorted(
            p.name
            for p in self.base.iterdir()
            if valid_id(p.name) and (p / "meta.json").is_file()
        )

    def meta(self, subject: str) -> Meta | None:
        """The subject's meta, or None when there is no such subject."""
        raw = read_json(self.dir(subject) / "meta.json", None)
        return Meta.from_json(raw) if isinstance(raw, dict) else None

    def need_meta(self, subject: str) -> Meta:
        """The meta, or ``bad_request`` for an unknown subject."""
        meta = self.meta(subject)
        if meta is None:
            msg = f"unknown subject {subject!r}"
            raise RequestError(BAD_REQUEST, msg)
        return meta

    def plan(self, subject: str) -> Plan | None:
        """The subject's plan, or None before one was drafted."""
        raw = read_json(self.dir(subject) / "plan.json", None)
        return Plan.from_json(raw) if isinstance(raw, dict) else None

    def cards(self, subject: str) -> dict[str, CardRec]:
        """Card id -> card, in file order (module order, then ``order``)."""
        raw = read_json(self.dir(subject) / "cards.json", {})
        if not isinstance(raw, dict):
            return {}
        return {
            cid: CardRec.from_json(card)
            for cid, card in raw.items()
            if valid_id(cid) and isinstance(card, dict)
        }

    def concepts(self, subject: str) -> list[dict[str, Any]]:
        """``[{"name","at","card","session"}]``, oldest first."""
        raw = read_json(self.dir(subject) / "concepts.json", [])
        return [c for c in raw if isinstance(c, dict)] if isinstance(raw, list) else []

    def profile_raw(self, subject: str) -> dict[str, Any] | None:
        """The subject's stored teaching profile (see ``profiles``), if any."""
        raw = read_json(self.dir(subject) / "profile.json", None)
        return raw if isinstance(raw, dict) else None

    def commit(self, subject: str, meta: Meta, change: Change | None = None) -> Meta:
        """Write the changed parts, then ``meta`` with ``rev`` + 1; returns it."""
        where = self.dir(subject)
        change = change or Change()
        plan, cards, concepts, profile = (
            change.plan,
            change.cards,
            change.concepts,
            change.profile,
        )
        with LOCK:
            if plan is not None:
                meta.plan_rev = plan.rev
                write_json(where / "plan.json", plan_json(plan))
            if cards is not None:
                ordered = self._ordered(cards, plan or self.plan(subject))
                write_json(where / "cards.json", ordered)
            if concepts is not None:
                write_json(where / "concepts.json", concepts)
            if profile is not None:
                write_json(where / "profile.json", profile)
            meta.rev += 1
            write_json(where / "meta.json", asdict(meta))
        return meta

    @staticmethod
    def _ordered(
        cards: dict[str, CardRec], plan: Plan | None
    ) -> dict[str, dict[str, Any]]:
        """Cards sorted by (module position in the plan, ``order``)."""
        rank = {m.id: i for i, m in enumerate(plan.modules)} if plan else {}
        keys = sorted(
            cards, key=lambda c: (rank.get(cards[c].module, len(rank)), cards[c].order)
        )
        return {cid: cards[cid].to_json() for cid in keys}
