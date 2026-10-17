# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Ids, ULIDs, the device id and the request error."""

from __future__ import annotations

import itertools
import json
from pathlib import Path
import re
import string
from typing import TYPE_CHECKING, Any
import unicodedata

import pytest

from tutor.curriculum import ids
from tutor.curriculum.errors import RequestError
from tutor.curriculum.ids import MAX_ID, device_id, slug, ulid, valid_eid, valid_id

if TYPE_CHECKING:
    from collections.abc import Collection


@pytest.mark.parametrize(
    ("value", "ok"),
    [
        ("car", True),
        ("how-a-car-works", True),
        ("a" * 48, True),
        ("a" * 49, False),
        ("Car", False),
        ("a--b", False),
        ("-a", False),
        ("", False),
        (3, False),
    ],
)
def test_valid_id(value: object, ok: bool) -> None:
    assert valid_id(value) is ok


def test_slug_cuts_at_a_word_and_dedupes() -> None:
    assert slug("How a Car works?") == "how-a-car-works"
    assert slug("x", {"x", "x-2"}) == "x-3"
    long = slug(" ".join(["word"] * 30))
    assert len(long) <= 45
    assert long.endswith("word")
    assert slug("!!!", fallback="item") == "item"
    assert slug("a" * 60) == "a" * 45


def test_ulid_is_sortable_and_valid() -> None:
    first, second = ulid(1000, b"\0" * 10), ulid(1001, b"\0" * 10)
    assert valid_eid(first)
    assert first < second
    assert len(ulid(5)) == 26
    assert ulid(5, b"\1") == ulid(5, b"\1" + b"\0" * 9)
    assert not valid_eid("x")


def test_device_id_is_written_once(tmp_path: Path) -> None:
    path = tmp_path / "d" / "device_id"
    first = device_id(path)
    assert device_id(path) == first
    path.write_text("\n", encoding="utf-8")
    assert device_id(path) != first


def test_request_error_codes() -> None:
    err = RequestError("plan_conflict", "reload")
    assert isinstance(err, ValueError)
    assert err.result(5) == {
        "ok": False,
        "at": 5,
        "code": "plan_conflict",
        "error": "reload",
        "retry": False,
    }
    with pytest.raises(ValueError, match="unknown error code"):
        RequestError("nope", "x")


def test_ulid_is_monotonic_within_a_millisecond(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = ulid(10_000)
    second = ulid(10_000)
    earlier = ulid(9_000)  # a clock step back still sorts after
    assert first < second < earlier
    monkeypatch.setattr(ids, "_MONO", [20_000, ids._MAX_RAND])
    assert ulid(20_000).startswith(ulid(20_000, b"\0")[:10])


_VECTORS = json.loads(
    (Path(__file__).parents[2] / "contract" / "slug_vectors.json").read_text(
        encoding="utf-8"
    )
)


@pytest.mark.parametrize("row", _VECTORS["slug"], ids=lambda r: r["slug"])
def test_slug_vectors_shared_with_dart(row: dict[str, str]) -> None:
    assert slug(row["text"]) == row["slug"]
    assert valid_id(row["slug"])


@pytest.mark.parametrize("row", _VECTORS["valid"], ids=lambda r: repr(r["id"]))
def test_valid_id_vectors_shared_with_dart(row: dict[str, Any]) -> None:
    assert valid_id(row["id"]) is row["ok"]


def test_vectors_still_hold_nfd_spellings() -> None:
    """An editor that re-normalizes the JSON would silently drop the NFD cases."""
    texts = [r["text"] for r in _VECTORS["slug"]]
    ids_ = [r["id"] for r in _VECTORS["valid"]]
    assert any(not unicodedata.is_normalized("NFC", t) for t in texts)
    assert any(not unicodedata.is_normalized("NFC", i) for i in ids_)


def test_slug_keeps_polish_letters() -> None:
    assert slug("Chcę rozumieć pojęcia z maila") == "chcę-rozumieć-pojęcia-z-maila"
    assert slug("ZAŻÓŁĆ GĘŚLĄ JAŹŃ") == "zażółć-gęślą-jaźń"


def test_slug_composes_nfd_so_one_word_is_one_id() -> None:
    nfc = "zażółć"
    nfd = unicodedata.normalize("NFD", nfc)
    assert nfd != nfc
    assert slug(nfd) == slug(nfc) == nfc
    assert not valid_id(nfd)
    assert unicodedata.is_normalized("NFC", slug(nfd))


def test_polish_ids_count_characters_not_bytes() -> None:
    assert valid_id("ą" * 48)
    assert not valid_id("ą" * 49)
    assert len(slug("ą" * 60)) == 45


def _old_slug(text: str, taken: Collection[str] = (), fallback: str = "item") -> str:
    """The ASCII-only slug() as it was before Polish letters were allowed."""
    words = [w for w in re.split(r"[^a-z0-9]+", text.casefold()) if w]
    base = ""
    for word in words:
        longer = f"{base}-{word}" if base else word
        if len(longer) > MAX_ID - 3:
            break
        base = longer
    base = base or (words[0][: MAX_ID - 3] if words else fallback)
    candidate, n = base, 2
    while candidate in taken:
        candidate = f"{base}-{n}"
        n += 1
    return candidate


def test_ascii_slugs_are_byte_identical_to_before() -> None:
    """Every short ASCII string over a nasty alphabet, plus word-cut cases."""
    texts = [
        "".join(chars)
        for n in range(6)
        for chars in itertools.product("aB1 -_!", repeat=n)
    ]
    texts += [" ".join(["word"] * n) for n in range(30)]
    texts += ["a" * n for n in (44, 45, 46, 47, 48, 49, 90)]
    texts += ["How a Car works?", "x" * 40 + " y z", string.printable]
    for text in texts:
        for taken in ((), {_old_slug(text), _old_slug(text) + "-2"}):
            assert slug(text, taken) == _old_slug(text, taken)
