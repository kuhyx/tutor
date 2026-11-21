# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Drain a redraft run: build each pending unit, swap it in, record the outcome.

One drainer per data dir (a ``flock`` on ``redraft/drain.lock``): the live
server's (``relay.redraft_task``), or ``python -m tutor redraft drain`` on a
copy. Units are built in parallel threads (they read the snapshot only);
every swap takes the subjects' process lock. The model is the draft tier
behind the reply cache (``replies``), and ``wait`` runs before every real
call: the live drainer waits there while a learner's reply is in flight.

An outage (``claude_unavailable``) leaves the unit pending and ends the
round (the caller tries again later; never a weaker model). Any other
failure counts a try; a bad model answer (``model_error``) also forgets the
unit's last cached answer, so the next try asks that one call again; after
three tries the unit is ``failed`` and its old cards stay live.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import fcntl
import logging
from typing import TYPE_CHECKING, Final

from tutor.curriculum.errors import CLAUDE_UNAVAILABLE, MODEL_ERROR, RequestError
from tutor.curriculum.redraft import run, swap, unit
from tutor.curriculum.redraft.replies import Cached
from tutor.curriculum.subject_store import write_json

if TYPE_CHECKING:
    from collections.abc import Callable

    from tutor.curriculum.context import Context
    from tutor.curriculum.redraft.run import Unit

WORKERS: Final = 4
_logger = logging.getLogger(__name__)


def _nothing() -> None:
    """The default ``wait``."""


def one(ctx: Context, todo: Unit, wait: Callable[[], None] = _nothing) -> Unit:
    """Build and swap one unit; returns it with its new state (also stored)."""
    here = run.root(ctx)
    cached = Cached(ctx.draft, here / "replies", wait)
    drafting = replace(ctx, model=cached, draft=cached)
    done = replace(todo, tries=todo.tries + 1, error="")
    try:
        snap = run.before(ctx, todo.subject)
        result = unit.build(drafting, snap, todo.module)
        out = here / "out" / todo.subject / f"{todo.module}.json"
        write_json(out, result.to_json())
        swapped = swap.apply(ctx, snap, result)
        write_json(out, {**result.to_json(), "swap": swapped})
        done.state = run.DONE
    except RequestError as err:
        done.error = err.message
        if err.code == CLAUDE_UNAVAILABLE:
            done.tries = todo.tries  # an outage is nobody's failed try
        else:
            if err.code == MODEL_ERROR:  # a bad answer: ask that call again
                for key in cached.used[-1:]:
                    cached.forget(key)
            if done.tries >= run.MAX_TRIES:
                done.state = run.FAILED
        _logger.warning("redraft %s: %s", todo.name, err.message)
    done.keys = cached.used
    run.update(ctx, done)
    _logger.warning(
        "redraft %s: %s (%d model calls)", todo.name, done.state, cached.calls
    )
    return done


def drain(
    ctx: Context,
    wait: Callable[[], None] = _nothing,
    workers: int = WORKERS,
    limit: int | None = None,
) -> list[Unit]:
    """One round over the pending units; returns them as they ended.

    ``limit``: at most this many units this round (the live server takes a
    few at a time and publishes them before the next round).

    Returns [] at once when another drainer holds this data dir. A unit
    still ``pending`` afterwards hit an outage or has tries left: call
    again later.
    """
    here = run.root(ctx)
    todo = run.pending(ctx)[:limit]
    if not todo:
        return []
    with (here / "drain.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            _logger.warning("redraft: another drainer holds %s", here)
            return []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(lambda u: one(ctx, u, wait), todo))
