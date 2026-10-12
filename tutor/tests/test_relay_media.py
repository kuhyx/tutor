# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Media for RTDB: IMG urls, inline SVG checks, old-picture URL resolution."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from tutor import commons, images
from tutor.relay import commons_url, media_out

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

PAGE = "https://commons.wikimedia.org/wiki/File:Relay_coil.jpg"
THUMB = "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Relay.jpg/800px-Relay.jpg"


def raw_image(**over: Any) -> dict[str, Any]:
    base = {
        "term": "relay",
        "title": "Relay coil.jpg",
        "file": "0123456789abcdef.jpg",
        "author": "A",
        "licence": "CC BY 4.0",
        "licence_url": "https://cc",
        "page_url": PAGE,
        "url": THUMB,
    }
    return {**base, **over}


def test_image_keeps_attribution_and_an_allowed_url() -> None:
    node = media_out.image(raw_image(url=THUMB + "?utm_source=x"), lambda _p: None)
    assert node["url"] == THUMB
    assert "file" not in node
    assert node["author"] == "A"
    thumb = "https://thumb.wikimedia.org/x/960px-y.png"
    assert media_out.image(raw_image(url=thumb), lambda _p: None)["url"] == thumb


def test_image_resolves_or_omits_the_url() -> None:
    old = raw_image(url="")
    assert (
        media_out.image(old, lambda page: THUMB if page == PAGE else None)["url"]
        == THUMB
    )
    assert "url" not in media_out.image(old, lambda _p: None)
    evil = raw_image(url="https://evil.example/x.jpg", title=None)
    node = media_out.image(evil, lambda _p: None)
    assert "url" not in node
    assert node["title"] == ""


def test_safe_svg() -> None:
    assert media_out.safe_svg('<svg><use href="#a"/><path d="M0"/></svg>')
    assert not media_out.safe_svg("<svg><script>x</script></svg>")
    assert not media_out.safe_svg("<svg><foreignObject/></svg>")
    assert not media_out.safe_svg('<svg onload="x()"></svg>')
    assert not media_out.safe_svg('<svg><image xlink:href="https://x/y.png"/></svg>')


def test_diagrams_inline_capped_and_checked(tmp_path: Path) -> None:
    good = "0123456789abcdef-0.svg"
    (tmp_path / good).write_text('<svg viewBox="0 0 1 1"><path d="M0 0"/></svg>')
    (tmp_path / "0123456789abcdef-1.svg").write_text("<svg><script/></svg>")
    (tmp_path / "0123456789abcdef-2.svg").write_text("<svg>" + "x" * 9000 + "</svg>")
    message = {
        "diagram_title": "Coil loop",
        "diagrams": [
            good,
            "0123456789abcdef-1.svg",
            "0123456789abcdef-2.svg",
            "0123456789abcdef-3.svg",  # missing
            "../etc/passwd",
            good,
            good,
        ],
    }
    got = media_out.diagrams_of(message, tmp_path)
    assert len(got) == media_out.MAX_DIAGRAMS
    assert got[0] == {
        "title": "Coil loop",
        "svg": '<svg viewBox="0 0 1 1"><path d="M0 0"/></svg>',
    }
    assert media_out.diagrams_of({}, tmp_path) == []
    assert media_out.diagram(good, "t") is None  # default cache: nothing there


def test_commons_url_resolves_once_and_remembers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fake_get(url: str) -> bytes:
        calls.append(url)
        pages = (
            {"1": {"imageinfo": [{"thumburl": THUMB}]}} if "Relay" in url else {"2": {}}
        )
        return json.dumps({"query": {"pages": pages}}).encode()

    monkeypatch.setattr(commons, "get", fake_get)
    assert commons_url.resolve("https://example.org/wiki/x") is None
    assert commons_url.resolve(PAGE) == THUMB
    assert commons_url.resolve(PAGE) == THUMB
    missing = "https://commons.wikimedia.org/wiki/File:Nothing.png"
    assert commons_url.resolve(missing) is None
    assert commons_url.resolve(missing) is None
    assert len(calls) == 2
    assert "iiurlwidth=800" in calls[0]


def test_commons_url_network_error_is_not_remembered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert commons_url.resolve(PAGE) is None  # the sandbox blocks urlopen
    assert not commons_url.cache_path().exists()
    commons_url.cache_path().parent.mkdir(parents=True)
    commons_url.cache_path().write_text("[1]")
    monkeypatch.setattr(commons, "get", lambda _u: b'{"query": {}}')
    assert commons_url.resolve(PAGE) is None
    commons_url.cache_path().write_text("{broken")
    assert commons_url.resolve(PAGE) is None


def test_commons_image_url_and_tolerant_cache_reads() -> None:
    img = images.CommonsImage(**{k: v for k, v in raw_image().items() if k != "url"})
    assert img.url == ""
    newer = images.CommonsImage.from_json({**raw_image(), "future_field": "x"})
    assert newer.url == THUMB
