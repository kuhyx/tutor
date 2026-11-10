# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Pinned subjects: cards only from the web pages the learner named.

A goal containing ``https://`` URLs pins the subject to those pages: the
planner is shown them and every card is drafted from one of them, never from
a wiki search. The page text comes from ``ctx.text`` (``sources.page_text``:
fetched once, cached on disk), which is also what the excerpt check reads, so
the model drafts from and the check verifies against one text. The hosts the
learner typed are the allowlist; nothing else is fetched.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import TYPE_CHECKING, Final
from urllib.parse import urlsplit

from tutor.curriculum import wiki
from tutor.curriculum.errors import BAD_REQUEST, RequestError

if TYPE_CHECKING:
    from collections.abc import Callable

MAX_PINNED: Final = 20
# Essays run long (a Paul Graham essay is ~7000 words); a wiki extract's
# 2500-word clip would hide most of one, and at most 3 are sent per module.
MAX_WORDS: Final = 8000
MAX_TITLE: Final = 80
_URL: Final = re.compile(r"https://[^\s<>\"'()\[\]{}]+")
_TRAILING: Final = ".,;:!?"


@dataclass(frozen=True)
class WebPage:
    """A pinned page: its URL, a title and the full cached text."""

    url: str
    title: str
    text: str


def pinned(goal: str) -> list[str]:
    """The ``https`` URLs in ``goal``, in order, each once, at most 20."""
    found = [m.group().rstrip(_TRAILING) for m in _URL.finditer(goal)]
    return list(dict.fromkeys(found))[:MAX_PINNED]


def without_urls(goal: str) -> str:
    """``goal`` with its URLs removed (the words that name the subject)."""
    return _URL.sub(" ", goal)


def title(text: str, url: str) -> str:
    """The page's first line (its ``<title>``), else the URL's last part."""
    first = " ".join(text.strip().split("\n", 1)[0].split())
    if first:
        return first[:MAX_TITLE]
    parts = urlsplit(url)
    return parts.path.rstrip("/").rsplit("/", 1)[-1] or parts.netloc


def fetch(text: Callable[[str], str], urls: list[str]) -> list[WebPage]:
    """Every pinned page, or a ``bad_request`` naming the one that failed."""
    pages: list[WebPage] = []
    for url in urls:
        try:
            body = text(url)
        except OSError as err:
            msg = f"cannot fetch {url}: {err}"
            raise RequestError(BAD_REQUEST, msg) from err
        if len(body) < wiki.MIN_CHARS:
            msg = f"{url} has too little text to teach from ({len(body)} chars)"
            raise RequestError(BAD_REQUEST, msg)
        pages.append(WebPage(url, title(body, url), body))
    return pages


def source(page: WebPage) -> wiki.Source:
    """The text the card drafter sees (clipped; the check reads it all)."""
    return wiki.Source(page.url, page.title, " ".join(page.text.split()[:MAX_WORDS]))


def listing(pages: list[WebPage], lead: int = 120) -> str:
    """The planner's view of the pinned pages: title, URL, first words."""
    shown = "\n\n".join(
        f'<page title="{p.title}" url="{p.url}">\n'
        f"{' '.join(p.text.split()[:lead])}\n</page>"
        for p in pages
    )
    return (
        "This subject is PINNED: every card is written ONLY from the pages "
        "below, not from Wikipedia or Wikibooks. Plan modules these pages "
        "cover well, each drawing on one or more of them; a module `title` "
        "names the idea plainly.\n\n" + shown
    )
