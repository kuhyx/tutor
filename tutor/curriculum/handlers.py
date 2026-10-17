# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The curriculum's public API for the relay worker (build lane).

``BUILD_HANDLERS[kind](body, ctx) -> data`` for the build-lane request kinds
(``DOCS-contract.md`` §4). Handlers block (model calls, page fetches): run
them in a worker thread, e.g. ``await asyncio.to_thread(handler, body, ctx)``.
A refusal raises :class:`RequestError` (``.code``, ``.message``,
``.result(at)``); anything else is a bug (``worker_error``).

After the log changed (and before each request) call
:func:`fold_and_advance`; then run :func:`generate` on the build lane for
each ``[subject, module]`` it returns in ``generate``. :func:`stats` builds
the ``stats`` node; :class:`EventLog` (``ctx.log``) mirrors RTDB
``log/{dev}`` and holds the worker's own ``taught`` events to publish.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from tutor.curriculum.advance import fold_and_advance, pending
from tutor.curriculum.card_edit import card_edit
from tutor.curriculum.card_undo import card_remove, card_restore
from tutor.curriculum.cardgen import generate
from tutor.curriculum.context import Context
from tutor.curriculum.errors import RequestError
from tutor.curriculum.eventlog import EventLog
from tutor.curriculum.plan_ops import (
    plan_approve,
    plan_edit,
    plan_revise,
    subject_finish,
    subject_new,
)
from tutor.curriculum.pregen import module_pregenerate
from tutor.curriculum.stats import stats

if TYPE_CHECKING:
    from collections.abc import Callable

    Handler = Callable[[dict[str, Any], Context], dict[str, Any]]

BUILD_HANDLERS: Final[dict[str, Handler]] = {
    "subject_new": subject_new,
    "plan_revise": plan_revise,
    "plan_edit": plan_edit,
    "plan_approve": plan_approve,
    "subject_finish": subject_finish,
    "card_edit": card_edit,
    "card_restore": card_restore,
    "card_remove": card_remove,
    "module_pregenerate": module_pregenerate,
}

__all__ = [
    "BUILD_HANDLERS",
    "Context",
    "EventLog",
    "RequestError",
    "fold_and_advance",
    "generate",
    "pending",
    "stats",
]
