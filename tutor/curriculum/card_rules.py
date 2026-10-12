# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The card rules for curriculum cards: exactly :mod:`tutor.cards`' rules.

A stored card becomes a ``cards.Card`` whose topic is its module (title and
id prefixes), so the field / word-count / https / prefix checks, the
``requires`` cycle check, the engine, the gating and the system prompt all
work on generated cards unchanged.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from tutor import cards
from tutor.curriculum import wiki

_logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from tutor.curriculum.context import Context
    from tutor.curriculum.records import CardRec, Module


def topic(module: Module) -> cards.Topic:
    """The module as a deck topic; no prefixes means any id is fine."""
    return cards.Topic(module.id, module.title, tuple(module.prefixes) or ("",))


def as_card(cid: str, rec: CardRec, module: Module) -> cards.Card:
    """``rec`` as a deck card; ``cards.CardError`` names what is wrong."""
    raw = {
        "id": cid,
        "front": rec.front,
        "back": rec.back,
        "source": rec.source,
        "excerpt": rec.excerpt,
        "requires": list(rec.requires),
    }
    return cards.validate_card(raw, topic(module), f"{module.id}/{cid}")


def check_set(found: dict[str, CardRec], modules: dict[str, Module]) -> None:
    """The whole subject: every card valid, every ``requires`` known, no cycle.

    ``cards.CardError`` (or a ``KeyError`` for an unknown module) on failure.
    """
    deck = [as_card(cid, rec, modules[rec.module]) for cid, rec in found.items()]
    cards.check_requires(deck)


def source_problem(ctx: Context, cid: str, rec: CardRec) -> str | None:
    """Why ``rec``'s excerpt is not in its source (fetched, cached), or None."""
    try:
        wiki.reseed(ctx.fetch, rec.source)
    except (OSError, ValueError) as err:
        _logger.warning("could not re-seed %s: %r", rec.source, err)
    mismatch = ctx.check(cid, rec.source, rec.excerpt)
    return None if mismatch is None else mismatch.reason
