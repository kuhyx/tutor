# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Every failed ``result`` carries a ``kind`` the app can draw (DOCS-relay-kinds.md)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tutor.curriculum.errors import CODES as CURRICULUM_CODES
from tutor.curriculum.errors import RequestError as CurriculumError
from tutor.relay import kinds
from tutor.relay.claims import PHASES
from tutor.relay.errors import CODES, RequestError, result_of

_GOLDEN = Path(__file__).resolve().parents[2] / "contract" / "relay_kinds.json"


@pytest.mark.parametrize("code", sorted(CODES))
def test_every_code_yields_a_kind(code: str) -> None:
    """``result_of`` adds a known kind for each contract code."""
    node = result_of(RequestError("x", code=code))
    assert node["kind"] in kinds.KINDS
    assert node["error"] == "x"  # the old sentence stays on the wire


@pytest.mark.parametrize(
    ("code", "extra", "kind"),
    [
        ("bad_request", {"reason": "paste_statement"}, "refused_paste_statement"),
        ("bad_request", {"reason": "other"}, "err_bad_request"),
        ("bad_request", {}, "err_bad_request"),
        (
            "no_card_left",
            {"next": "review_module", "module": "m2"},
            "blocked_no_card_review",
        ),
        ("no_card_left", {"next": "reviews_due", "due_at": 1}, "blocked_no_card_due"),
        ("no_card_left", {"next": "none"}, "blocked_no_card_none"),
        ("no_card_left", {}, "blocked_no_card_none"),
        ("locked", {"next": "review_module", "module": "m1"}, "blocked_locked_review"),
        ("locked", {"next": "none"}, "blocked_locked"),
        ("daily_new_cap", {"next": "lift_cap"}, "blocked_cap"),
        ("claude_unavailable", {"reason": "rate_limit"}, "outage_claude"),
        ("claude_unavailable", {"reason": "network"}, "outage_claude"),
        ("model_error", {}, "err_model"),
        ("worker_error", {}, "err_worker"),
    ],
)
def test_kind_follows_code_reason_and_next(
    code: str, extra: dict[str, object], kind: str
) -> None:
    """Reason and next split a code into its cases; reason/next stay on the wire."""
    node = result_of(RequestError("x", code=code, extra=extra))
    assert node["kind"] == kind
    assert {k: node[k] for k in extra} == extra


def test_an_unknown_reason_goes_out_as_other() -> None:
    """``tutor.codes`` closes ``reason``; the kind is the plain code's."""
    node = result_of(RequestError("x", code="bad_request", extra={"reason": "new"}))
    assert (node["reason"], node["kind"]) == ("other", "err_bad_request")


def test_unknown_code_is_a_worker_error() -> None:
    """A code outside the contract reads as ``worker_error``."""
    assert result_of(RequestError("x", code="nope"))["kind"] == "err_worker"
    assert kinds.kind_of("nope") == "err_worker"


def test_odd_reason_or_next_splits_nothing() -> None:
    """A list or number in ``reason`` / ``next`` keeps the plain kind."""
    assert kinds.kind_of("bad_request", ["paste_statement"]) == "err_bad_request"
    assert kinds.kind_of("no_card_left", None, {"x": 1}) == "blocked_no_card_none"


def test_extra_never_overrides_kind() -> None:
    """A stray ``kind`` in ``extra`` cannot replace the computed one."""
    err = RequestError("x", code="model_error", extra={"kind": "blocked_cap"})
    assert result_of(err)["kind"] == "err_model"


@pytest.mark.parametrize("code", sorted(CURRICULUM_CODES))
def test_curriculum_result_has_kind(code: str) -> None:
    """The curriculum error's own result node carries the kind too."""
    node = CurriculumError(code, "x").result(5)
    assert node["kind"] == kinds.kind_of(code)


def test_golden_matches_mapping() -> None:
    """``contract/relay_kinds.json`` is what ``scripts/gen_relay_kinds.py`` writes."""
    assert json.loads(_GOLDEN.read_text(encoding="utf-8")) == kinds.golden(PHASES)


def test_golden_rows_cover_every_kind_and_code() -> None:
    """Each kind has a row, each code has a row, and each row maps as stated."""
    rows = kinds.golden_rows()
    assert {r["kind"] for r in rows} == set(kinds.KINDS)
    assert {r["code"] for r in rows} >= CODES
    for r in rows:
        assert kinds.kind_of(r["code"], r.get("reason"), r.get("next")) == r["kind"]
