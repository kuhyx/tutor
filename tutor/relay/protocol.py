# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Validation of every request read from RTDB (``DOCS-contract.md`` §4, §10).

All RTDB content is untrusted: ids are checked against their regexes before
any path or file name is built from them, sizes are capped, and unknown
fields are dropped (the handler only ever sees the fields named here).
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import TYPE_CHECKING, Any, Final

from tutor import delivery
from tutor.history import SESSION_ID
from tutor.relay.errors import RequestError

if TYPE_CHECKING:
    from collections.abc import Callable

RID: Final = re.compile(r"[0-9A-HJKMNP-TV-Z]{26}", re.ASCII)
DEV: Final = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
SLUG: Final = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*", re.ASCII)
SLUG_MAX: Final = 48
MAX_REQUEST_BYTES: Final = 40_000
MAX_MESSAGE: Final = 8000
MAX_TEXT: Final = 2000
MAX_CARD_FIELD: Final = 2000

CHAT: Final = "chat"
BUILD: Final = "build"


def _slug(value: object) -> str:
    if isinstance(value, str) and len(value) <= SLUG_MAX and SLUG.fullmatch(value):
        return value
    raise ValueError


def _opt_slug(value: object) -> str | None:
    return None if value is None else _slug(value)


def _session(value: object) -> str:
    if isinstance(value, str) and SESSION_ID.fullmatch(value):
        return value
    raise ValueError


def _text(limit: int, *, empty: bool = False) -> Callable[[object], str]:
    def check(value: object) -> str:
        if isinstance(value, str) and (empty or value.strip()) and len(value) <= limit:
            return value
        raise ValueError

    return check


def _is_ms(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _int(value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    raise ValueError


def _bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    raise ValueError


def _opt_bool(value: object) -> bool:
    return False if value is None else _bool(value)


def _ulid(value: object) -> str:
    if isinstance(value, str) and RID.fullmatch(value):
        return value
    raise ValueError


def _choice(value: object) -> str:
    if value in {"go_deeper", "review_only"}:
        return str(value)
    raise ValueError


def _slugs(value: object) -> list[str]:
    if isinstance(value, list) and len(value) <= SLUG_MAX:
        return [_slug(v) for v in value]
    raise ValueError


def _requires(value: object) -> list[str]:
    """Card ids; absent means none, since RTDB stores no empty arrays."""
    return [] if value is None else _slugs(value)


def _module_ids(value: object) -> list[str] | str:
    """``"all"`` or a non-empty list of module ids (``module_pregenerate``)."""
    if value == "all":
        return "all"
    if isinstance(value, list) and value:
        return _slugs(value)
    raise ValueError


def _modules(value: object) -> list[dict[str, Any]]:
    """Shape only; the curriculum validates the modules themselves."""
    if isinstance(value, list) and all(isinstance(m, dict) for m in value):
        return value
    raise ValueError


# kind -> (lane, field -> validator). Missing fields are validated as None.
KINDS: Final[dict[str, tuple[str, dict[str, Callable[[object], object]]]]] = {
    "subject_new": (BUILD, {"text": _text(MAX_TEXT)}),
    "plan_revise": (
        BUILD,
        {"subject": _slug, "plan_rev": _int, "comment": _text(MAX_TEXT)},
    ),
    "plan_edit": (BUILD, {"subject": _slug, "plan_rev": _int, "modules": _modules}),
    "plan_approve": (BUILD, {"subject": _slug, "plan_rev": _int}),
    "subject_finish": (BUILD, {"subject": _slug, "choice": _choice}),
    "module_pregenerate": (BUILD, {"subject": _slug, "modules": _module_ids}),
    "card_edit": (
        BUILD,
        {
            "subject": _slug,
            "card": _opt_slug,
            "module": _slug,
            "front": _text(MAX_CARD_FIELD, empty=True),
            "back": _text(MAX_CARD_FIELD, empty=True),
            "source": _text(MAX_CARD_FIELD, empty=True),
            "excerpt": _text(MAX_CARD_FIELD, empty=True),
            "requires": _requires,
        },
    ),
    # ``device``: "phone" | "desktop", absent = desktop (``tutor.delivery``).
    "session_start": (
        CHAT,
        {
            "subject": _opt_slug,
            "card": _opt_slug,
            "resume": _opt_bool,
            "device": delivery.device,
        },
    ),
    "session_resume": (CHAT, {"session": _session, "device": delivery.device}),
    "message": (
        CHAT,
        {"session": _session, "text": _text(MAX_MESSAGE), "device": delivery.device},
    ),
    "next": (CHAT, {"session": _session, "device": delivery.device}),
    "stop": (CHAT, {"session": _session}),
    "card_done": (CHAT, {"subject": _opt_slug, "card": _slug, "done": _bool}),
    # The model-free drill (``tutor.drill``): served while Claude is not.
    "drill_next": (CHAT, {"subject": _opt_slug}),
    "drill_answer": (CHAT, {"prompt_id": _ulid, "choice": _int}),
    "anki_status": (CHAT, {}),
}


@dataclass(frozen=True)
class Request:
    """One validated request; ``created`` is RTDB server time (ms)."""

    rid: str
    kind: str
    lane: str
    dev: str
    created_ms: int
    sent_at_ms: int | None
    body: dict[str, Any]


def _bad(why: str) -> RequestError:
    return RequestError(why, code="bad_request")


def _body(kind: str, raw: object) -> dict[str, Any]:
    fields = KINDS[kind][1]
    given = raw if isinstance(raw, dict) else {}
    body: dict[str, Any] = {}
    for name, check in fields.items():
        try:
            body[name] = check(given.get(name))
        except ValueError:
            why = f"{kind}: field {name!r} is missing or invalid"
            raise _bad(why) from None
    return body


def _problem(req: object) -> str | None:
    """What is wrong with a request's envelope, or ``None``."""
    if not isinstance(req, dict):
        return "request is not an object"
    if len(json.dumps(req)) > MAX_REQUEST_BYTES:
        return "request too large"
    kind = req.get("kind")
    if not isinstance(kind, str) or kind not in KINDS:
        return f"unknown request kind {str(kind)[:40]!r}"
    dev = req.get("dev")
    if not isinstance(dev, str) or not DEV.fullmatch(dev):
        return "bad device id"
    sent = req.get("sent_at")
    if not _is_ms(req.get("created")) or (sent is not None and not _is_ms(sent)):
        return "bad created/sent_at time"
    return None


def validate(rid: str, req: object) -> Request:
    """The request at ``requests/{rid}/req``, or ``RequestError(bad_request)``.

    ``rid`` itself is checked by the caller (an invalid rid gets no result:
    no path is built from it).
    """
    if (why := _problem(req)) is not None:
        raise _bad(why)
    fields = req if isinstance(req, dict) else {}
    kind, dev = str(fields["kind"]), str(fields["dev"])
    sent = fields.get("sent_at")
    created_ms, sent_ms = int(fields["created"]), None if sent is None else int(sent)
    return Request(
        rid,
        kind,
        KINDS[kind][0],
        dev,
        created_ms,
        sent_ms,
        _body(kind, fields.get("body")),
    )


def valid_rid(rid: str) -> bool:
    """Whether ``rid`` is a ULID (the only keys a path is built from)."""
    return bool(RID.fullmatch(rid))
