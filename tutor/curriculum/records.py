# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The curriculum records, field for field as ``DOCS-contract-curriculum.md``.

``from_json`` validates types, ids and sizes and raises ``RequestError``
(``bad_request``) on anything else; unknown keys are dropped. ``to_json`` is
the exact contract shape (the PC file and the RTDB projection are the same).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
import json
from typing import Any, Final

from tutor.curriculum.errors import BAD_REQUEST, RequestError
from tutor.curriculum.ids import valid_id

SUBJECT_STATUS: Final = frozenset(
    {"drafting", "draft", "active", "completed", "review_only", "failed"}
)
MODULE_STATUS: Final = frozenset(
    {"locked", "generating", "ready", "mastered", "failed"}
)
ORIGINS: Final = frozenset({"seed", "generated", "edited"})
MAX_TITLE: Final = 120
MAX_SUMMARY: Final = 300
MAX_NOTES: Final = 600
MAX_GOAL: Final = 2000
MAX_PLAN_BYTES: Final = 16_000
MAX_CARD_BYTES: Final = 2_000
MIN_MODULES: Final = 3
MAX_MODULES: Final = 12


def bad(message: str) -> RequestError:
    """A ``bad_request`` error."""
    return RequestError(BAD_REQUEST, message)


def text(raw: dict[str, Any], key: str, limit: int, *, empty: bool = False) -> str:
    """``raw[key]`` as a stripped string of at most ``limit`` characters."""
    value = raw.get(key, "")
    if not isinstance(value, str) or len(value.strip()) > limit:
        msg = f"{key} must be a string of at most {limit} characters"
        raise bad(msg)
    if not empty and not value.strip():
        msg = f"{key} must not be empty"
        raise bad(msg)
    return value.strip()


def id_list(raw: object, what: str) -> list[str]:
    """A list of distinct valid ids."""
    if not isinstance(raw, list) or not all(valid_id(i) for i in raw):
        msg = f"{what} must be a list of ids"
        raise bad(msg)
    if len(set(raw)) != len(raw):
        msg = f"{what} has duplicates"
        raise bad(msg)
    return list(raw)


def _int(raw: dict[str, Any], key: str, default: int = 0) -> int:
    value = raw.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool):
        msg = f"{key} must be an integer"
        raise bad(msg)
    return value


@dataclass
class Meta:
    """``subjects/{subj}/meta``."""

    title: str
    goal: str
    status: str
    created: int
    plan_rev: int = 0
    rev: int = 0
    origin: str = "generated"
    error: str | None = None

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> Meta:
        """Validated meta (local file)."""
        status = raw.get("status")
        if status not in SUBJECT_STATUS:
            msg = f"unknown subject status {status!r}"
            raise bad(msg)
        return cls(
            title=text(raw, "title", MAX_TITLE),
            goal=text(raw, "goal", MAX_GOAL),
            status=str(status),
            created=_int(raw, "created"),
            plan_rev=_int(raw, "plan_rev"),
            rev=_int(raw, "rev"),
            origin=str(raw.get("origin", "generated")),
            error=e if isinstance(e := raw.get("error"), str) else None,
        )


@dataclass
class Module:
    """One plan module; array order is teaching order."""

    id: str
    title: str
    summary: str = ""
    requires: list[str] = field(default_factory=list)
    depth: int = 1
    prefixes: list[str] = field(default_factory=list)
    status: str = "locked"
    recall: float = 0.0
    cards: int = 0
    error: str | None = None
    pregenerated: bool = False  # cards drafted ahead, still locked for study

    @classmethod
    def from_json(cls, raw: object, *, client: bool = False) -> Module:
        """A module; ``client`` input keeps only the editable fields."""
        if not isinstance(raw, dict) or not valid_id(raw.get("id")):
            msg = (
                "a module needs a valid id (a-z, 0-9, ąćęłńóśźż and -; <=48 characters)"
            )
            raise bad(msg)
        prefixes = raw.get("prefixes", [])
        if not isinstance(prefixes, list) or not all(
            isinstance(p, str) and p for p in prefixes
        ):
            msg = "prefixes must be a list of strings"
            raise bad(msg)
        module = cls(
            id=str(raw["id"]),
            title=text(raw, "title", MAX_TITLE),
            summary=text(raw, "summary", MAX_SUMMARY, empty=True),
            requires=id_list(raw.get("requires", []), "requires"),
            depth=max(1, _int(raw, "depth", 1)),
            prefixes=list(prefixes),
        )
        if not client:
            status = raw.get("status", "locked")
            if status not in MODULE_STATUS:
                msg = f"unknown module status {status!r}"
                raise bad(msg)
            module.status = str(status)
            module.recall = float(raw.get("recall", 0.0))
            module.cards = _int(raw, "cards")
            error = raw.get("error")
            module.error = error if isinstance(error, str) else None
            module.pregenerated = raw.get("pregenerated") is True
        return module


@dataclass
class Plan:
    """``subjects/{subj}/plan``."""

    rev: int
    status: str
    notes: str
    modules: list[Module]
    history: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> Plan:
        """Validated plan (local file)."""
        mods = raw.get("modules")
        history = raw.get("history", [])
        if not isinstance(mods, list) or not isinstance(history, list):
            msg = "plan needs a modules list"
            raise bad(msg)
        return cls(
            rev=_int(raw, "rev"),
            status="approved" if raw.get("status") == "approved" else "draft",
            notes=text(raw, "notes", MAX_NOTES, empty=True),
            modules=[Module.from_json(m) for m in mods],
            history=[h for h in history if isinstance(h, dict)],
        )

    def module(self, module_id: str) -> Module | None:
        """The module with ``module_id``, if any."""
        return next((m for m in self.modules if m.id == module_id), None)


def check_modules(modules: list[Module]) -> None:
    """Unique ids, ``requires`` only on earlier modules, 3-12 per draft.

    The count is of the newest draft (the deepest ``depth``): go-deeper
    rounds append modules to a plan that already has some.
    """
    newest = max((m.depth for m in modules), default=1)
    count = sum(m.depth == newest for m in modules)
    if not MIN_MODULES <= count <= MAX_MODULES:
        msg = f"a plan draft has {MIN_MODULES}-{MAX_MODULES} modules, not {count}"
        raise bad(msg)
    seen: set[str] = set()
    for module in modules:
        if module.id in seen:
            msg = f"duplicate module id {module.id!r}"
            raise bad(msg)
        late = [r for r in module.requires if r not in seen]
        if late:
            msg = f"{module.id} requires {late}, which are not earlier modules"
            raise bad(msg)
        seen.add(module.id)


@dataclass
class CardRec:
    """``subjects/{subj}/cards/{cid}`` (the id is the key, not a field)."""

    module: str
    order: int
    front: str
    back: str
    source: str
    excerpt: str
    requires: list[str] = field(default_factory=list)
    rev: int = 1
    origin: str = "generated"
    created: int = 0
    suspended: bool = False
    tutor: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> CardRec:
        """A stored card (local file; validated by ``card_rules`` on write)."""
        known = {f.name: raw[f.name] for f in fields(cls) if f.name in raw}
        return cls(**known)

    def to_json(self) -> dict[str, Any]:
        """The contract shape; refuses a card over the 2 KB budget."""
        out = {k: v for k, v in asdict(self).items() if v or k != "tutor"}
        if len(json.dumps(out, ensure_ascii=False).encode()) > MAX_CARD_BYTES:
            msg = f"card is over {MAX_CARD_BYTES} bytes"
            raise bad(msg)
        return out


def plan_json(plan: Plan) -> dict[str, Any]:
    """The plan's contract shape (``pregenerated`` only when set); <= 16 KB."""
    out = asdict(plan)
    for module in out["modules"]:  # an unset flag keeps the old shape
        if not module["pregenerated"]:
            del module["pregenerated"]
    if len(json.dumps(out, ensure_ascii=False).encode()) > MAX_PLAN_BYTES:
        msg = f"plan is over {MAX_PLAN_BYTES} bytes"
        raise bad(msg)
    return out
