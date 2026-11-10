# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Machine codes beside the spoken sentences: one closed vocabulary per surface.

``contract/codes.json`` is the golden vector the Dart mirror also reads; every
vocabulary here must equal what the server actually emits.
"""

from __future__ import annotations

import json
from pathlib import Path

from claude_agent_sdk import ClaudeSDKError
import pytest

from tutor import clock, codes, outage, unavailable
from tutor.curriculum import errors as cur_errors
from tutor.relay import claims
from tutor.relay import errors as relay_errors
from tutor.session import SessionError

CONTRACT = Path(__file__).resolve().parents[2] / "contract" / "codes.json"


def test_the_contract_file_is_the_module() -> None:
    raw = json.loads(CONTRACT.read_text(encoding="utf-8"))
    raw.pop("_doc")
    assert raw == codes.vocabulary()


def test_each_vocabulary_is_what_the_server_emits() -> None:
    assert relay_errors.CODES | {codes.OTHER} == codes.RELAY_CODE
    assert cur_errors.CODES <= codes.RELAY_CODE
    assert codes.RELAY_PHASE == claims.PHASES
    assert codes.UNAVAILABLE_REASON == unavailable.REASONS
    assert {outage.RATE_LIMIT, outage.OVERLOADED, outage.NETWORK} == (
        unavailable.REASONS
    )
    assert codes.PAUSE_REASON == {
        "low_effort": clock.LOW_EFFORT,
        "stalled": clock.STALLED,
    }
    # A failed result's ``reason``: the coach's paste prompt, or the outage's.
    assert (
        {codes.PASTE_STATEMENT, codes.OTHER} | unavailable.REASONS
    ) == codes.FAIL_REASON
    for vocab in (codes.FAIL_REASON, codes.NOTICE_KIND, codes.ERROR_KIND):
        assert codes.OTHER in vocab


@pytest.mark.parametrize(
    ("err", "kind"),
    [
        (outage.ClaudeUnavailableError("rate_limit", 5), "claude_limit"),
        (outage.ClaudeUnavailableError("overloaded"), "claude_overloaded"),
        (outage.ClaudeUnavailableError("network"), "claude_network"),
        (SessionError("crashed"), "model_failed"),
        (ClaudeSDKError("cli died"), "model_failed"),
        (TimeoutError(), "model_failed"),
        (cur_errors.RequestError("model_error", "bad json"), "model_failed"),
        (cur_errors.RequestError("bad_request", "no"), "bad_request"),
        (cur_errors.RequestError("plan_conflict", "rev"), "other"),
        (RuntimeError("boom"), "other"),
    ],
)
def test_error_kind_by_exception_type(err: BaseException, kind: str) -> None:
    assert codes.error_kind(err) == kind


def test_error_kind_follows_a_kept_outage_cause() -> None:
    inner = outage.ClaudeUnavailableError("rate_limit", 9)
    err = cur_errors.RequestError("claude_unavailable", str(inner))
    err.__cause__ = inner  # what ``modelcall`` raises ``from`` the outage
    assert codes.error_kind(err) == "claude_limit"


def test_every_failed_result_carries_its_error_kind() -> None:
    gone = relay_errors.classify(outage.ClaudeUnavailableError("overloaded", 7))
    node = relay_errors.result_of(gone)
    assert (node["code"], node["reason"]) == ("claude_unavailable", "overloaded")
    assert node["error_kind"] == "claude_overloaded"
    model = relay_errors.result_of(relay_errors.classify(SessionError("x")))
    assert (model["code"], model["error_kind"]) == ("model_error", "model_failed")
    worker = relay_errors.result_of(relay_errors.classify(KeyError("k")))
    assert (worker["code"], worker["error_kind"]) == ("worker_error", "other")
    paste = relay_errors.RequestError(
        "paste it", code="bad_request", extra={"reason": codes.PASTE_STATEMENT}
    )
    assert relay_errors.result_of(paste)["reason"] == "paste_statement"


def test_an_unlisted_reason_reports_other() -> None:
    odd = relay_errors.RequestError("x", code="bad_request", extra={"reason": "zzz"})
    assert relay_errors.result_of(odd)["reason"] == codes.OTHER


def test_kind_parsers_map_unknown_to_other() -> None:
    assert codes.closed(codes.NOTICE_KIND, "removed") == "removed"
    assert codes.closed(codes.NOTICE_KIND, "exploded") == codes.OTHER
    assert codes.closed(codes.ERROR_KIND, None) == codes.OTHER


def test_records_round_trip_the_error_kind() -> None:
    from tutor.curriculum.records import Meta, Module

    meta = Meta.from_json(
        {"title": "T", "goal": "G", "status": "failed", "created": 1}
        | {"error": "down", "error_kind": "claude_limit"}
    )
    assert meta.error_kind == "claude_limit"
    odd = Meta.from_json(
        {"title": "T", "goal": "G", "status": "failed", "created": 1}
        | {"error": "down", "error_kind": "zzz"}
    )
    assert odd.error_kind == codes.OTHER
    old = Meta.from_json({"title": "T", "goal": "G", "status": "draft", "created": 1})
    assert old.error_kind is None
    mod = Module.from_json(
        {"id": "a", "title": "A", "status": "failed", "error": "x"}
        | {"error_kind": "too_few_cards"}
    )
    assert mod.error_kind == "too_few_cards"
    assert Module.from_json({"id": "a", "title": "A"}).error_kind is None
