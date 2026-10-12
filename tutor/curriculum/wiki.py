# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Find card sources without giving the model tools: the MediaWiki API.

Looks up exact titles (redirects followed) and searches en.wikipedia.org and
en.wikibooks.org for candidate pages (``candidates``); ``relevance`` and the
model then pick the on-topic ones, and ``seed`` puts a chosen page's
plain-text extract into the excerpt-check cache (``sources.seed_text``), so
the model drafts from exactly the text that ``sources.check_excerpt`` later
verifies. API answers are cached on disk;
requests carry a descriptive User-Agent (Wikimedia's API etiquette).
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final
from urllib.parse import quote, unquote, urlencode, urlsplit
import urllib.request

from tutor import sources

if TYPE_CHECKING:
    from collections.abc import Callable

    FetchFn = Callable[[str], bytes]

WIKIPEDIA: Final = "en.wikipedia.org"
WIKIBOOKS: Final = "en.wikibooks.org"
USER_AGENT: Final = "tutor-curriculum/0.1 (https://github.com/kuhyx/tutor)"
MIN_CHARS: Final = 1500
MAX_WORDS: Final = 2500
MAX_SOURCES: Final = 3
MAX_CANDIDATES: Final = 8
_TIMEOUT: Final = 20
# Per query: how many search hits to look at on each wiki.
_SEARCH: Final = ((WIKIPEDIA, 4), (WIKIBOOKS, 3))
_LISTY: Final = (
    "list of",
    "lists of",
    "index of",
    "outline of",
    "timeline of",
    "glossary of",
    "bibliography of",
)


@dataclass(frozen=True)
class Source:
    """One fetched page: its URL, title and the text the model sees."""

    url: str
    title: str
    text: str


@dataclass(frozen=True)
class Page:
    """A candidate page: its full extract, and whether an exact-title hit."""

    host: str
    title: str
    text: str
    exact: bool

    @property
    def url(self) -> str:
        """The article URL a card cites."""
        return page_url(self.host, self.title)


def cache_dir() -> Path:
    """The API cache (``TUTOR_WIKI_CACHE``, else ``~/.cache/tutor/wiki``)."""
    override = os.environ.get("TUTOR_WIKI_CACHE")
    return Path(override) if override else Path.home() / ".cache/tutor/wiki"


def http_get(url: str) -> bytes:
    """GET ``url`` (https MediaWiki API only) with the tutor's User-Agent."""
    if not url.startswith(("https://en.wikipedia.org/", "https://en.wikibooks.org/")):
        msg = f"not a MediaWiki API URL: {url}"
        raise ValueError(msg)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
        body: bytes = response.read()
    return body


def api(fetch: FetchFn, host: str, params: dict[str, Any]) -> dict[str, Any]:
    """One API query (JSON, formatversion 2), cached on disk by URL."""
    query = urlencode({**params, "format": "json", "formatversion": "2"})
    url = f"https://{host}/w/api.php?{query}"
    cached = cache_dir() / hashlib.sha256(url.encode()).hexdigest()[:24]
    if cached.is_file():
        body = cached.read_bytes()
    else:
        body = fetch(url)
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(body)
    data = json.loads(body)
    return data if isinstance(data, dict) else {}


def search(fetch: FetchFn, host: str, query: str, limit: int) -> list[str]:
    """Titles of the top ``limit`` search hits."""
    data = api(
        fetch,
        host,
        {"action": "query", "list": "search", "srsearch": query, "srlimit": limit},
    )
    hits = data.get("query", {}).get("search", [])
    return [str(h["title"]) for h in hits if isinstance(h, dict) and "title" in h]


def extract(fetch: FetchFn, host: str, title: str) -> str:
    """The page's plain-text extract ("" when there is none)."""
    params = {"action": "query", "prop": "extracts", "explaintext": 1, "titles": title}
    pages = api(fetch, host, params).get("query", {}).get("pages", [])
    text = pages[0].get("extract", "") if pages and isinstance(pages[0], dict) else ""
    return text if isinstance(text, str) else ""


def page_url(host: str, title: str) -> str:
    """The article URL a card cites."""
    return f"https://{host}/wiki/{quote(title.replace(' ', '_'))}"


def article(url: str) -> tuple[str, str] | None:
    """``(host, title)`` of a Wikipedia / Wikibooks article URL, else None."""
    parts = urlsplit(url)
    host = parts.hostname or ""
    if host not in {WIKIPEDIA, WIKIBOOKS} or not parts.path.startswith("/wiki/"):
        return None
    return host, unquote(parts.path.removeprefix("/wiki/")).replace("_", " ")


def reseed(fetch: FetchFn, url: str) -> None:
    """Re-seed an uncached wiki article's extract (cache wiped or moved).

    A generated card's excerpt was checked against the extract; without
    this a later re-check would compare it with the HTML page instead.
    """
    found = article(url)
    if found is None or sources.is_cached(url):
        return
    text = extract(fetch, *found)
    if text:
        sources.seed_text(url, text)


def _clip(text: str) -> str:
    words = text.split()
    return " ".join(words[:MAX_WORDS])


def _listy(title: str) -> bool:
    """Index-like pages (lists, outlines, disambiguation): never a source."""
    lowered = title.lower()
    return lowered.startswith(_LISTY) or "(disambiguation)" in lowered


def page(fetch: FetchFn, host: str, title: str, *, exact: bool) -> Page | None:
    """``title`` after redirects, or None: missing, disambiguation, too short."""
    params = {
        "action": "query",
        "prop": "extracts|pageprops",
        "ppprop": "disambiguation",
        "explaintext": 1,
        "redirects": 1,
        "titles": title,
    }
    pages = api(fetch, host, params).get("query", {}).get("pages", [])
    found = pages[0] if pages and isinstance(pages[0], dict) else {}
    text, name = found.get("extract"), found.get("title")
    if "disambiguation" in (found.get("pageprops") or {}):
        return None
    if not isinstance(text, str) or len(text) < MIN_CHARS or not isinstance(name, str):
        return None
    return None if _listy(name) else Page(host, name, text, exact=exact)


def candidates(fetch: FetchFn, titles: list[str], queries: list[str]) -> list[Page]:
    """Pages that may cover a module, canonical ones first.

    ``titles`` are looked up exactly on Wikipedia (redirects followed: the
    canonical article); then each query's search hits on Wikipedia and
    Wikibooks, in search-ranking order. Index-like, disambiguation and short
    pages are dropped; at most ``MAX_CANDIDATES``, one per URL.
    """
    wanted = [(WIKIPEDIA, t, True) for t in titles]
    for query in queries:
        for host, tries in _SEARCH:
            wanted += [(host, t, False) for t in search(fetch, host, query, tries)]
    found: dict[str, Page] = {}
    for host, title, exact in wanted:
        if len(found) >= MAX_CANDIDATES or _listy(title):
            continue
        hit = page(fetch, host, title, exact=exact)
        if hit is not None and hit.url not in found:
            found[hit.url] = hit
    return list(found.values())


def seed(chosen: Page) -> Source:
    """Seed the excerpt-check cache with ``chosen``; the text the model sees."""
    checked = sources.seed_text(chosen.url, chosen.text)
    return Source(chosen.url, chosen.title, _clip(checked))
