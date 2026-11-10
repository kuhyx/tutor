# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Small helpers shared by the focus handlers (``focus``, ``focus_interview``)."""

from __future__ import annotations

import contextlib
from datetime import UTC, date, datetime
import re
from typing import TYPE_CHECKING
import unicodedata

from tutor import credit, focus_hook
from tutor.relay.errors import RequestError

if TYPE_CHECKING:
    from collections.abc import Iterator

    from tutor.focus_hook import FocusApi
    from tutor.relay.context import RequestContext


def load_api() -> FocusApi:
    """The ``focus_project`` module, or a ``worker_error`` when it is missing."""
    found = focus_hook.load_fp()
    if found is None:
        msg = "focus_project is not installed on the worker"
        raise RequestError(msg, code="worker_error")
    return found


def today_of(ctx: RequestContext) -> date:
    """The PC-local day of the request."""
    return date.fromisoformat(credit.local_day(ctx.now())[0])


def naive_local(ts: float) -> datetime:
    """``ts`` as a naive local datetime, the shape focus_project takes."""
    return datetime.fromtimestamp(ts, tz=UTC).astimezone().replace(tzinfo=None)


def local_now(ctx: RequestContext) -> datetime:
    """The request time as a naive local datetime."""
    return naive_local(ctx.now())


def unreadable(exc: Exception) -> RequestError:
    """A registry or evidence file that cannot be read: retry as a new rid."""
    return RequestError(
        f"focus registry unreadable: {exc}", code="worker_error", retry=True
    )


def slug_of(name: str) -> str:
    """An ascii lowercase slug of ``name`` (``project`` if nothing is left)."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")[:40].strip("-")
    return slug or "project"


def free_id(name: str, taken: set[str]) -> str:
    """A slug of ``name`` not in ``taken`` (``-2``, ``-3`` ... appended)."""
    base = slug_of(name)
    found, n = base, 1
    while found in taken:
        n += 1
        found = f"{base}-{n}"
    return found


@contextlib.contextmanager
def registry() -> Iterator[None]:
    """focus_project's refusals as results: ValueError / KeyError come back loud."""
    try:
        yield
    except KeyError as exc:
        msg = f"unknown project {exc.args[0]!r}"
        raise RequestError(msg, code="focus_refused") from exc
    except ValueError as exc:
        raise RequestError(str(exc), code="focus_refused") from exc
    except OSError as exc:
        raise unreadable(exc) from exc
