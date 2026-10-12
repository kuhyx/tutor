# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Find card sources without giving the model tools: the MediaWiki API.

Searches en.wikipedia.org and en.wikibooks.org, takes the plain-text extract
of the best long-enough pages and seeds the excerpt-check cache with it
(``sources.seed_text``), so the model drafts from exactly the text that
``sources.check_excerpt`` later verifies. API answers are cached on disk;
requests carry a descriptive User-Agent (Wikimedia's API etiquette).
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final
from urllib.parse import quote, urlencode
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
_TIMEOUT: Final = 20
# Per query: how many search hits to try on each wiki, and how many to keep.
_PLAN: Final = ((WIKIPEDIA, 4, 2), (WIKIBOOKS, 3, 1))


@dataclass(frozen=True)
class Source:
    """One fetched page: its URL, title and the text the model sees."""

    url: str
    title: str
    text: str


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


def _clip(text: str) -> str:
    words = text.split()
    return " ".join(words[:MAX_WORDS])


def find_sources(fetch: FetchFn, queries: list[str]) -> list[Source]:
    """Up to 3 long-enough pages for ``queries``, Wikipedia first."""
    found: list[Source] = []
    seen: set[str] = set()
    for query in queries:
        for host, tries, keep in _PLAN:
            kept = 0
            for title in search(fetch, host, query, tries):
                url = page_url(host, title)
                if kept >= keep or len(found) >= MAX_SOURCES or url in seen:
                    continue
                seen.add(url)
                text = extract(fetch, host, title)
                if len(text) < MIN_CHARS:
                    continue
                checked = sources.seed_text(url, text)
                found.append(Source(url, title, _clip(checked)))
                kept += 1
    return found
