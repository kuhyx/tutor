# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""MediaWiki sources: search, extracts, cache, the excerpt-cache seed."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Self
from urllib.parse import parse_qs, urlsplit
import urllib.request

import pytest

from tutor import sources
from tutor.curriculum import wiki

if TYPE_CHECKING:
    from pathlib import Path

LONG = "Pistons move. " * 200


class FakeWiki:
    """host -> {"search": {query: [titles]}, "pages": {title: extract}}.

    A page value may also be ``{"to": title}`` (a redirect) or
    ``{"extract": text, "disambiguation": True}``.
    """

    def __init__(self) -> None:
        self.data: dict[str, dict[str, Any]] = {
            wiki.WIKIPEDIA: {"search": {}, "pages": {}},
            wiki.WIKIBOOKS: {"search": {}, "pages": {}},
        }
        self.calls: list[str] = []

    def __call__(self, url: str) -> bytes:
        self.calls.append(url)
        parts = urlsplit(url)
        q = {k: v[0] for k, v in parse_qs(parts.query).items()}
        site = self.data[parts.hostname or ""]
        if q.get("list") == "search":
            titles = site["search"].get(q["srsearch"], [])
            body: Any = {
                "query": {"search": [{"title": t} for t in titles] + [{"x": 1}]}
            }
            return json.dumps(body).encode()
        title = q["titles"]
        found = site["pages"].get(title)
        if isinstance(found, dict) and "to" in found and q.get("redirects"):
            title = found["to"]
            found = site["pages"].get(title)
        page: dict[str, Any] = {"title": title}
        if found is None:
            page["missing"] = True
        elif isinstance(found, str):
            page["extract"] = found
        else:
            page["extract"] = found.get("extract", "")
            if found.get("disambiguation"):
                page["pageprops"] = {"disambiguation": ""}
        return json.dumps({"query": {"pages": [page]}}).encode()


@pytest.fixture
def fake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeWiki:
    monkeypatch.setattr(sources, "CACHE_DIR", tmp_path / "src-cache")
    monkeypatch.setenv("TUTOR_WIKI_CACHE", str(tmp_path / "wiki"))
    return FakeWiki()


def test_candidates_exact_titles_first_then_search(fake: FakeWiki) -> None:
    pedia, books = fake.data[wiki.WIKIPEDIA], fake.data[wiki.WIKIBOOKS]
    pedia["pages"].update(
        {
            "Automobile": {"to": "Car"},
            "Car": LONG,
            "Mercury": {"extract": LONG, "disambiguation": True},
            "Engine": LONG,
            "Short": "tiny",
            "List of cars": LONG,
        }
    )
    pedia["search"]["car"] = ["Car", "Short", "List of cars", "Engine"]
    books["search"]["car"] = ["Book/Chapter"]
    books["pages"]["Book/Chapter"] = LONG + " extra words " * 3000
    found = wiki.candidates(fake, ["Automobile", "Mercury", "Nowhere"], ["car"])
    assert [(p.title, p.exact) for p in found] == [
        ("Car", True),
        ("Engine", False),
        ("Book/Chapter", False),
    ]
    assert found[0].url == "https://en.wikipedia.org/wiki/Car"
    assert found[2].url == "https://en.wikibooks.org/wiki/Book/Chapter"
    assert not any("List_of" in c or "List+of" in c for c in fake.calls)
    calls = len(fake.calls)
    assert wiki.candidates(fake, ["Automobile"], ["car"])  # all cached now
    assert len(fake.calls) == calls


def test_candidates_cap_and_seed(
    fake: FakeWiki, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(wiki, "MAX_CANDIDATES", 2)
    for name in ("A", "B", "C"):
        fake.data[wiki.WIKIPEDIA]["pages"][name] = LONG + " more words " * 3000
    found = wiki.candidates(fake, ["A", "B", "C"], [])
    assert [p.title for p in found] == ["A", "B"]
    chosen = wiki.seed(found[0])
    assert len(chosen.text.split()) == wiki.MAX_WORDS
    assert sources.page_text(chosen.url) == found[0].text  # the check sees it


def test_seed_keeps_an_already_cached_page(fake: FakeWiki) -> None:
    url = wiki.page_url(wiki.WIKIPEDIA, "Old page")
    assert url.endswith("/wiki/Old_page")
    sources.seed_text(url, "first text")
    fake.data[wiki.WIKIPEDIA]["pages"]["Old page"] = LONG
    (hit,) = wiki.candidates(fake, ["Old page"], [])
    assert wiki.seed(hit).text == "first text"


def test_missing_pages_and_odd_answers(
    fake: FakeWiki, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake.data[wiki.WIKIPEDIA]["search"]["q"] = ["Gone"]
    assert wiki.candidates(fake, [], ["q"]) == []
    monkeypatch.setattr(wiki, "api", lambda *_: {"query": {"pages": ["x"]}})
    assert wiki.extract(fake, wiki.WIKIPEDIA, "t") == ""
    assert wiki.page(fake, wiki.WIKIPEDIA, "t", exact=True) is None
    monkeypatch.setattr(wiki, "api", lambda *_: {"query": {"pages": [{"extract": 3}]}})
    assert wiki.extract(fake, wiki.WIKIPEDIA, "t") == ""
    untitled = {"query": {"pages": [{"extract": LONG}]}}
    monkeypatch.setattr(wiki, "api", lambda *_: untitled)
    assert wiki.page(fake, wiki.WIKIPEDIA, "t", exact=True) is None
    listy = {"query": {"pages": [{"extract": LONG, "title": "Outline of cars"}]}}
    monkeypatch.setattr(wiki, "api", lambda *_: listy)
    assert wiki.page(fake, wiki.WIKIPEDIA, "Cars outline", exact=True) is None
    disamb = {"title": "X (disambiguation)", "extract": LONG, "pageprops": None}
    monkeypatch.setattr(wiki, "api", lambda *_: {"query": {"pages": [disamb]}})
    assert wiki.page(fake, wiki.WIKIPEDIA, "X", exact=False) is None


def test_api_non_object_answer(fake: FakeWiki) -> None:
    assert wiki.api(lambda _: b"[1]", wiki.WIKIPEDIA, {"a": 1}) == {}


def test_http_get_refuses_other_hosts() -> None:
    with pytest.raises(ValueError, match="not a MediaWiki API URL"):
        wiki.http_get("https://example.org/w/api.php")


def test_http_get_sends_the_user_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[Any] = []

    class _Response:
        def __enter__(self) -> Self:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def read(self) -> bytes:
            return b"{}"

    def fake_open(request: Any, timeout: int) -> _Response:
        seen.append((request.get_header("User-agent"), timeout))
        return _Response()

    monkeypatch.setattr(urllib.request, "urlopen", fake_open)
    assert wiki.http_get("https://en.wikipedia.org/w/api.php?x=1") == b"{}"
    assert seen == [(wiki.USER_AGENT, 20)]


def test_cache_dir_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("TUTOR_WIKI_CACHE", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert wiki.cache_dir() == tmp_path / ".cache/tutor/wiki"


def test_article_and_reseed(fake: FakeWiki) -> None:
    assert wiki.article("https://example.org/wiki/X") is None
    assert wiki.article("https://en.wikipedia.org/w/index.php") is None
    url = "https://en.wikipedia.org/wiki/Disc_brake"
    assert wiki.article(url) == (wiki.WIKIPEDIA, "Disc brake")
    wiki.reseed(fake, "https://example.org/x")
    empty = "https://en.wikipedia.org/wiki/Empty"
    wiki.reseed(fake, empty)  # no extract: nothing cached
    assert not sources.is_cached(empty)
    fake.data[wiki.WIKIPEDIA]["pages"]["Disc brake"] = LONG
    wiki.reseed(fake, url)
    assert sources.page_text(url) == LONG
    calls = len(fake.calls)
    wiki.reseed(fake, url)  # cached: no fetch
    assert len(fake.calls) == calls
