# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Load and validate the deck's topic files.

One JSON file per topic under ``deck/``, the topics listed in its
``manifest.json`` (:data:`TOPICS`). Each card names the URL it was written
from and a verbatim excerpt of that page; ``sources.check_excerpt`` is what
proves the excerpt is really there.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Final
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Topic:
    """A topic file: its subdeck title and the prefix every card id carries."""

    stem: str
    title: str
    prefixes: tuple[str, ...]


REPO_DECK: Final = Path(__file__).resolve().parents[1] / "subjects/automation/deck"
# The tests pin card ids, so they read a frozen deck (``tests/fixtures/deck``,
# set by the repo ``conftest.py``); everything else reads the repo deck.
DECK_DIR: Final = Path(os.environ.get("TUTOR_DECK_DIR") or REPO_DECK)
MANIFEST: Final = "manifest.json"


def topics(deck_dir: Path) -> tuple[Topic, ...]:
    """The deck's topics in teaching order, from its ``manifest.json``.

    The manifest is a JSON array of ``{"stem", "title", "prefixes"}``; the
    redraft's deck export (``redraft.deck``) rewrites it when a topic is cut.
    """
    raw = json.loads((deck_dir / MANIFEST).read_text(encoding="utf-8"))
    return tuple(Topic(t["stem"], t["title"], tuple(t["prefixes"])) for t in raw)


TOPICS: Final = topics(DECK_DIR)
_KEYS: Final = frozenset({"id", "front", "back", "source", "excerpt"})
# Optional: ids of cards that must be done before this one opens in the tutor.
# Anki has no gating, so deck.py ignores it.
_REQUIRES: Final = "requires"
# Optional: a memory aid shown under the answer. It states no fact of its own,
# so it is never excerpt-checked (``DOCS-contract-struggle.md`` §1).
_MNEMONIC: Final = "mnemonic"
_MAX_MNEMONIC_WORDS: Final = 40
# Optional: a code skeleton shown under the answer, newlines and indentation
# kept. Like the mnemonic it is never excerpt-checked; the 2 KB card budget
# (``records.MAX_CARD_BYTES``) bounds it.
_CODE: Final = "code"
_MAX_FRONT_WORDS: Final = 25
_MAX_BACK_WORDS: Final = 30
_EXCERPT_WORDS: Final = (6, 40)


class CardError(ValueError):
    """A topic file breaks the card format."""


@dataclass(frozen=True)
class Card:
    """One note: a question, its answer and the evidence for it."""

    id: str
    front: str
    back: str
    source: str
    excerpt: str
    topic: Topic
    requires: tuple[str, ...] = ()
    mnemonic: str = ""  # a memory aid; never excerpt-checked
    code: str = ""  # a code skeleton, layout kept; never excerpt-checked

    @property
    def source_host(self) -> str:
        """The source's host without ``www.``, used as the card's source tag."""
        return (urlsplit(self.source).hostname or "").removeprefix("www.")


def _words(text: str) -> int:
    return len(text.split())


def _validate(raw: object, topic: Topic, where: str) -> Card:
    """Build a card from one JSON object, or say exactly what is wrong."""
    optional = {_REQUIRES, _MNEMONIC, _CODE}
    if not isinstance(raw, dict) or not _KEYS <= set(raw) <= _KEYS | optional:
        msg = (
            f"{where}: a card must be an object with exactly {sorted(_KEYS)}"
            f" and optionally {_REQUIRES!r}, {_MNEMONIC!r}, {_CODE!r}"
        )
        raise CardError(msg)
    if not all(isinstance(raw[key], str) and raw[key].strip() for key in _KEYS):
        msg = f"{where}: every field must be a non-empty string"
        raise CardError(msg)
    requires = _requires(raw.get(_REQUIRES, []), where)
    card = Card(
        topic=topic,
        requires=requires,
        mnemonic=_mnemonic(raw, where),
        code=_code(raw, where),
        **{key: raw[key].strip() for key in _KEYS},
    )
    problems = []
    if card.id in card.requires:
        problems.append("a card cannot require itself")
    if not card.id.startswith(topic.prefixes):
        problems.append(f"id must start with one of {topic.prefixes}")
    if urlsplit(card.source).scheme != "https" or not urlsplit(card.source).hostname:
        problems.append("source must be an https URL")
    if _words(card.front) > _MAX_FRONT_WORDS:
        problems.append(f"front is over {_MAX_FRONT_WORDS} words")
    if _words(card.back) > _MAX_BACK_WORDS:
        problems.append(f"back is over {_MAX_BACK_WORDS} words")
    low, high = _EXCERPT_WORDS
    if not low <= _words(card.excerpt) <= high:
        problems.append(f"excerpt must be {low}-{high} words")
    if problems:
        msg = f"{where} ({card.id}): " + "; ".join(problems)
        raise CardError(msg)
    return card


def _mnemonic(raw: dict[str, object], where: str) -> str:
    """The optional memory aid, trimmed ("" when absent): one line, <= 40 words."""
    value = raw.get(_MNEMONIC, "")
    if _MNEMONIC in raw and not (isinstance(value, str) and value.strip()):
        msg = f"{where}: mnemonic must be a non-empty string"
        raise CardError(msg)
    text = str(value).strip()
    if any(end in text for end in "\r\n"):
        msg = f"{where}: mnemonic must be one line"
        raise CardError(msg)
    if _words(text) > _MAX_MNEMONIC_WORDS:
        msg = f"{where}: mnemonic is over {_MAX_MNEMONIC_WORDS} words"
        raise CardError(msg)
    return text


def _code(raw: dict[str, object], where: str) -> str:
    """The optional skeleton ("" when absent), trailing whitespace dropped."""
    value = raw.get(_CODE, "")
    if _CODE in raw and not (isinstance(value, str) and value.strip()):
        msg = f"{where}: code must be a non-empty string"
        raise CardError(msg)
    return str(value).rstrip()


def _requires(raw: object, where: str) -> tuple[str, ...]:
    """The optional ``requires`` list: distinct, non-empty card id strings."""
    items = raw if isinstance(raw, list) else [None]
    ids = tuple(i.strip() for i in items if isinstance(i, str) and i.strip())
    if len(ids) != len(items) or len(set(ids)) != len(ids):
        msg = f"{where}: {_REQUIRES} must be a list of distinct card ids"
        raise CardError(msg)
    return ids


def _check_requires(cards: list[Card]) -> None:
    """Every required id names a card of the deck, and no chain loops back."""
    by_id = {card.id: card for card in cards}
    for card in cards:
        unknown = [i for i in card.requires if i not in by_id]
        if unknown:
            msg = f"{card.id} requires unknown card(s) {unknown}"
            raise CardError(msg)
    finished: set[str] = set()

    def visit(card: Card, path: list[str]) -> None:
        if card.id in path:
            msg = "requires cycle: " + " -> ".join([*path, card.id])
            raise CardError(msg)
        if card.id not in finished:
            for need in card.requires:
                visit(by_id[need], [*path, card.id])
            finished.add(card.id)

    for card in cards:
        visit(card, [])


def validate_card(raw: object, topic: Topic, where: str) -> Card:
    """One card from its JSON object, by the deck's rules (``CardError``)."""
    return _validate(raw, topic, where)


def check_requires(cards: list[Card]) -> None:
    """Every ``requires`` id is a card of ``cards`` and no chain loops back."""
    _check_requires(cards)


def load_topic(path: Path, topic: Topic) -> list[Card]:
    """Every card in one topic file."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        msg = f"{path.name}: the file must hold a JSON array of cards"
        raise CardError(msg)
    return [_validate(item, topic, f"{path.name}[{i}]") for i, item in enumerate(raw)]


def load_deck(deck_dir: Path) -> list[Card]:
    """Every card of every topic, with ids unique across the whole deck."""
    cards: list[Card] = []
    # A deck dir with its own manifest names its topics (the repo deck after
    # a redraft); one without (a test's partial copy) has the default ones.
    own = (deck_dir / MANIFEST).is_file()
    for topic in topics(deck_dir) if own else TOPICS:
        path = deck_dir / f"{topic.stem}.json"
        if not path.is_file():
            msg = f"missing topic file {path}"
            raise CardError(msg)
        cards.extend(load_topic(path, topic))
    seen: set[str] = set()
    for card in cards:
        if card.id in seen:
            msg = f"duplicate card id {card.id}"
            raise CardError(msg)
        seen.add(card.id)
    _check_requires(cards)
    return cards
