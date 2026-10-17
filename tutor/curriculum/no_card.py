# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The ``no_card_left`` refusal: the subject's title and the next step.

``DOCS-contract.md`` §4: the shown ``error`` names the subject by its title
(never its slug) and says what to do; the result node also carries
``subject_title`` and ``next`` (``review_module`` with ``module`` and
``module_title``, ``reviews_due`` with ``due_at`` in ms, or ``none``) so
the app can offer the step itself. ``rules.pick`` decides which one.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

from tutor.curriculum.errors import NO_CARD_LEFT, RequestError

if TYPE_CHECKING:
    from tutor.curriculum.records import Module

REVIEW_MODULE: Final = "review_module"
REVIEWS_DUE: Final = "reviews_due"
NONE: Final = "none"
_WRITING: Final = " and the next module's cards are still being written"


def _when(ms: int) -> str:
    """``ms`` as PC-local ``YYYY-MM-DD HH:MM``."""
    return (
        datetime.fromtimestamp(ms / 1000, tz=UTC)
        .astimezone()
        .strftime("%Y-%m-%d %H:%M")
    )


def no_card_left(
    title: str,
    *,
    module: Module | None,
    due_at: int | None,
    writing: bool,
    now_ms: int,
) -> RequestError:
    """The error for a subject with no card to teach.

    ``module``: an open module fully taught but not yet reviewed (first
    choice); ``due_at``: the earliest review due among its taught cards;
    ``writing``: a module's cards are being generated right now.
    """
    name = title or "This subject"
    extra: dict[str, object] = {"subject_title": title}
    tail = _WRITING if writing else ""
    if module is not None:
        extra |= {"next": REVIEW_MODULE, "module": module.id}
        extra["module_title"] = module.title
        msg = (
            f"{name} — all cards of “{module.title}” are taught. "
            "Review them to open the next module."
        )
    elif due_at is not None:
        extra |= {"next": REVIEWS_DUE, "due_at": due_at}
        step = (
            "Reviews are due now."
            if due_at <= now_ms
            else f"The next review is due {_when(due_at)}."
        )
        msg = f"{name} — every open card is taught{tail}. {step}"
    else:
        extra["next"] = NONE
        msg = f"{name} — no card is open right now{tail}."
    return RequestError(NO_CARD_LEFT, msg, extra=extra)
