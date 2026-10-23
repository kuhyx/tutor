# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Request fields of struggle help: ``session_start.struggle``, ``card_edit.mnemonic``."""

from __future__ import annotations

import pytest

from tutor.relay import protocol
from tutor.relay.errors import RequestError
from tutor.tests.test_relay_protocol import RID, req

EDIT = {
    "subject": "car",
    "card": "c",
    "module": "engine",
    "front": "f",
    "back": "b",
    "source": "https://x",
    "excerpt": "e",
}


def test_session_start_struggle_defaults_to_false() -> None:
    plain = protocol.validate(RID, req("session_start", subject=None, card="c"))
    assert plain.body["struggle"] is False
    help_ = req("session_start", subject="car", card="c", struggle=True)
    assert protocol.validate(RID, help_).body["struggle"] is True
    with pytest.raises(RequestError):
        protocol.validate(RID, req("session_start", card="c", struggle="yes"))


def test_card_edit_mnemonic_absent_is_none_and_text_passes() -> None:
    assert protocol.validate(RID, req("card_edit", **EDIT)).body["mnemonic"] is None
    for text in ("", "Seal-in: the motor holds its own Start."):
        got = protocol.validate(RID, req("card_edit", **EDIT, mnemonic=text))
        assert got.body["mnemonic"] == text
    with pytest.raises(RequestError):
        protocol.validate(RID, req("card_edit", **EDIT, mnemonic=3))
