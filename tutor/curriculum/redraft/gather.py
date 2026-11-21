# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""A redraft's sources: the pages the old cards cite, plus a fresh search.

Cited pages first, most-cited first (their text is what the old excerpts
were checked against, re-seeded from the wiki extract where it is one), then
whatever ``cardgen``'s own source search finds for the module today (the
learner's pinned pages for a pinned subject, else a wiki search). A page
that cannot be read is skipped; a failed fresh search costs nothing as long
as one cited page is readable.
"""

from __future__ import annotations

from collections import Counter
import logging
from typing import TYPE_CHECKING, Final

from tutor.curriculum import cardgen, webpages, wiki

if TYPE_CHECKING:
    from tutor.curriculum.context import Context
    from tutor.curriculum.plan_context import Scope
    from tutor.curriculum.records import CardRec

MAX_CITED: Final = 10
CITED_WORDS: Final = 5000
_logger = logging.getLogger(__name__)


def _cited(ctx: Context, url: str) -> wiki.Source | None:
    """One cited page as a source, or None when it cannot be read."""
    try:
        wiki.reseed(ctx.fetch, url)
        text = ctx.text(url)
    except (OSError, ValueError) as err:
        _logger.warning("redraft: cannot read cited page %s: %r", url, err)
        return None
    found = wiki.article(url)
    title = found[1] if found else webpages.title(text, url)
    return wiki.Source(url, title, " ".join(text.split()[:CITED_WORDS]))


def gather(ctx: Context, scope: Scope, old: dict[str, CardRec]) -> list[wiki.Source]:
    """The sources a module is redrafted from ([] when none is readable)."""
    counted = Counter(c.source for c in old.values())
    pages = [_cited(ctx, url) for url, _ in counted.most_common(MAX_CITED)]
    found = [p for p in pages if p is not None]
    fresh = cardgen.sources(ctx, scope)
    if isinstance(fresh, str):
        _logger.warning("redraft: no fresh sources for %s: %s", scope.module.id, fresh)
        fresh = []
    have = {s.url for s in found}
    return found + [s for s in fresh if s.url not in have]
