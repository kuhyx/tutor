# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Pictures and diagrams as RTDB carries them (``DOCS-contract.md`` §8).

Nothing binary goes to RTDB. A picture is its Commons thumbnail URL plus
attribution (clients hotlink ``upload.wikimedia.org`` only); a diagram is its
schemdraw SVG inline, at most 8 KB, and only after a check that it holds no
script, no ``foreignObject`` and no reference outside itself.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any, Final

from tutor import diagrams

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

# Commons serves thumbnails from both hosts (2026-10: thumb.*, 960 px buckets).
IMAGE_HOSTS: Final = ("https://upload.wikimedia.org/", "https://thumb.wikimedia.org/")
MAX_SVG: Final = 8 * 1024
MAX_DIAGRAMS: Final = 2
_FIELD_MAX: Final = 500
_NAME: Final = re.compile(r"[0-9a-f]{16}-\d\.svg", re.ASCII)
_FORBIDDEN: Final = re.compile(
    r"<\s*script|<\s*foreignObject|\bon\w+\s*=", re.IGNORECASE
)
_HREF: Final = re.compile(r"""\bhref\s*=\s*["']([^"']*)["']""", re.IGNORECASE)
_IMG_FIELDS: Final = ("title", "author", "licence", "licence_url", "page_url", "term")
_logger = logging.getLogger(__name__)


def image(raw: dict[str, Any], resolve: Callable[[str], str | None]) -> dict[str, Any]:
    """The ``IMG`` node for a page message's picture.

    ``url`` is the cached Commons thumbnail URL, else resolved from the file
    page (pictures cached before the relay), else left out: the client then
    shows the attribution and link only.
    """
    node = {k: str(raw.get(k) or "")[:_FIELD_MAX] for k in _IMG_FIELDS}
    url = str(raw.get("url") or "") or (resolve(node["page_url"]) or "")
    url = url.split("?", 1)[0]  # Commons appends utm_* tracking parameters
    if url.startswith(IMAGE_HOSTS):
        node["url"] = url
    return node


def safe_svg(svg: str) -> bool:
    """No script, event handler, ``foreignObject`` or non-local ``href``."""
    if _FORBIDDEN.search(svg):
        return False
    return all(ref.startswith("#") for ref in _HREF.findall(svg))


def diagram(name: str, title: str, cache: Path | None = None) -> dict[str, str] | None:
    """The ``DGM`` node for a rendered diagram file, or ``None`` (dropped)."""
    if not _NAME.fullmatch(name):
        return None
    path = (cache or diagrams.cache_dir()) / name
    try:
        svg = path.read_text(encoding="utf-8")
    except OSError as err:
        _logger.warning("diagram %s not published: %s", name, err)
        return None
    if len(svg.encode()) > MAX_SVG or not safe_svg(svg):
        _logger.warning("diagram %s not published: too big or unsafe", name)
        return None
    return {"title": title[:_FIELD_MAX], "svg": svg}


def diagrams_of(
    message: dict[str, Any], cache: Path | None = None
) -> list[dict[str, str]]:
    """Up to :data:`MAX_DIAGRAMS` publishable diagrams of a page message."""
    title = str(message.get("diagram_title") or "")
    found = (diagram(str(n), title, cache) for n in message.get("diagrams") or [])
    return [d for d in found if d is not None][:MAX_DIAGRAMS]
