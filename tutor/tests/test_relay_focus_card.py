# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``focus_event`` ``card``: a graded check-in card is a tutor heartbeat."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from tutor.relay.errors import RequestError
from tutor.tests._focus_support import (
    CREATED,
    HOUR_MS,
    NOW,
    call,
    install_fake_fp,
    project,
)

if TYPE_CHECKING:
    from tutor.tests._fake_fp import FakeFp


@pytest.fixture
def fp(monkeypatch: pytest.MonkeyPatch) -> FakeFp:
    fake = install_fake_fp(monkeypatch)
    fake.projects = [project("now", 0, 3, subjects=("sql",))]
    return fake


def _card(ts: int, subject: str = "sql", card: str = "joins") -> dict[str, Any]:
    return {
        "event": "card",
        "ts": ts,
        "platform": "pc",
        "subject": subject,
        "card": card,
    }


def _refused(body: dict[str, Any]) -> RequestError:
    with pytest.raises(RequestError) as caught:
        call("focus_event", body)
    assert caught.value.code == "bad_request"
    return caught.value


def test_a_card_is_a_tutor_heartbeat_at_the_answer_time(fp: FakeFp) -> None:
    got = call("focus_event", _card(CREATED - 30_000))
    assert fp.activity == [
        {"source": "tutor", "kind": "heartbeat", "ts": NOW - 30.0, "dev": "pc"}
    ]
    assert got["name"] == "Now"


def test_a_card_ts_is_clamped_and_aged_like_a_tap(fp: FakeFp) -> None:
    call("focus_event", _card(CREATED + 5 * HOUR_MS))
    assert fp.activity[0]["ts"] == NOW
    _refused(_card(CREATED - 48 * HOUR_MS - 1))
    assert len(fp.activity) == 1


def test_a_card_of_a_subject_outside_the_project_is_refused(fp: FakeFp) -> None:
    _refused(_card(CREATED, subject="go", card="chan"))
    assert fp.activity == []


def test_an_unknown_card_is_refused(fp: FakeFp) -> None:
    _refused(_card(CREATED, card="nope"))
    assert fp.activity == []


def test_a_card_with_no_active_project_is_refused(fp: FakeFp) -> None:
    fp.projects = []
    _refused(_card(CREATED))
    assert fp.activity == []


@pytest.mark.parametrize("missing", ["subject", "card"])
def test_a_card_needs_its_subject_and_card(fp: FakeFp, missing: str) -> None:
    body = _card(CREATED)
    del body[missing]
    _refused(body)
    assert fp.activity == []


def test_a_bad_card_id_is_refused_at_validation(fp: FakeFp) -> None:
    _refused(_card(CREATED, card="../x"))
    assert fp.activity == []


def test_the_frozen_app_checkin_still_counts(fp: FakeFp) -> None:
    call("focus_event", {"event": "checkin", "ts": CREATED, "platform": "phone"})
    assert fp.activity[0]["kind"] == "checkin"


def test_an_unreadable_registry_is_a_retryable_worker_error(fp: FakeFp) -> None:
    fp.boom = OSError("disk")
    with pytest.raises(RequestError) as caught:
        call("focus_event", _card(CREATED))
    assert (caught.value.code, caught.value.retry) == ("worker_error", True)
    assert fp.activity == []
