# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Seed a mastered SQL lesson concept's FSRS cards (``curriculum.sql_cards``)."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from tutor.curriculum import sql_cards
from tutor.curriculum.sql_engine import run_query
from tutor.relay import hooks

if TYPE_CHECKING:
    from tutor.relay.context import RequestContext

_logger = logging.getLogger(__name__)


async def seed_cards(ctx: RequestContext, concept: str) -> None:
    """Cards for the concept just mastered; a failure is logged, never raised.

    The lesson state is already saved when this runs, so a failure here must
    not fail (and retry) the turn.
    """
    try:
        got = await asyncio.to_thread(
            sql_cards.seed_concept, ctx.engine.ctx, concept, run_query
        )
    except hooks.BASE_ERRORS:  # cards are a bonus: the lesson goes on
        _logger.exception("sql cards for %r were not added", concept)
        return
    if got.added:
        _logger.info("sql cards for %r: %s", concept, ", ".join(got.added))
