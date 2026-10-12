# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Thumbnail URLs for pictures cached before ``CommonsImage.url`` existed.

Old transcripts name a picture by its Commons file page only. Its 800 px
thumbnail URL is asked of the Commons API once and remembered in
``~/.cache/tutor/commons_urls.json`` (a miss is remembered too; a network
error is not, so it is retried on the next publish).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
import urllib.parse

from tutor import commons

_logger = logging.getLogger(__name__)
_PAGE_PREFIX = "https://commons.wikimedia.org/wiki/"


def cache_path() -> Path:
    """Where resolved URLs are remembered (resolved at call time)."""
    return Path.home() / ".cache" / "tutor" / "commons_urls.json"


def _load(path: Path) -> dict[str, str | None]:
    if not path.is_file():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except OSError, ValueError:
        _logger.warning("%s unreadable; resolving afresh", path)
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _ask(title: str) -> str | None:
    query = urllib.parse.urlencode(
        {
            "action": "query",
            "format": "json",
            "titles": title,
            "prop": "imageinfo",
            "iiprop": "url",
            "iiurlwidth": "800",
        }
    )
    data = json.loads(commons.get(f"{commons.API}?{query}"))
    for page in data.get("query", {}).get("pages", {}).values():
        info = (page.get("imageinfo") or [{}])[0]
        if info.get("thumburl"):
            return str(info["thumburl"])
    return None


def resolve(page_url: str) -> str | None:
    """The thumbnail URL of the file page ``page_url``, or ``None``."""
    if not page_url.startswith(_PAGE_PREFIX):
        return None
    path = cache_path()
    known = _load(path)
    if page_url in known:
        return known[page_url]
    title = urllib.parse.unquote(page_url.removeprefix(_PAGE_PREFIX))
    try:
        url = _ask(title)
    except (OSError, ValueError) as err:
        _logger.warning("could not resolve %s: %s", page_url, err)
        return None
    known[page_url] = url
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(known), encoding="utf-8")
    tmp.replace(path)
    return url
