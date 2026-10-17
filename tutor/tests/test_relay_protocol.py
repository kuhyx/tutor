# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Request validation, error codes and the done-map."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from claude_agent_sdk import ClaudeSDKError
import pytest

from tutor.curriculum.errors import RequestError as CurriculumError
from tutor.relay import errors, protocol
from tutor.relay.done import KEEP_S, DoneMap
from tutor.relay.errors import RequestError, classify, result_of
from tutor.session import SessionError

if TYPE_CHECKING:
    from pathlib import Path

RID = "01M4RBCX52MMHCK7K73E6KV90H"
DEV = "107cb1bf-a093-416a-b356-a995e13f73fe"
SID = "20261012-172346-1a58"


def req(kind: str = "message", **body: Any) -> dict[str, Any]:
    body = body or {"session": SID, "text": "hi"}
    return {"kind": kind, "dev": DEV, "created": 5000, "sent_at": 4000, "body": body}


def code_of(raw: object) -> str:
    with pytest.raises(RequestError) as err:
        protocol.validate(RID, raw)
    return err.value.code


def test_valid_message_drops_unknown_fields() -> None:
    raw = req(session=SID, text="hello", extra="x")
    raw["junk"] = 1
    got = protocol.validate(RID, raw)
    assert (got.kind, got.lane, got.dev) == ("message", "chat", DEV)
    assert (got.created_ms, got.sent_at_ms) == (5000, 4000)
    assert got.body == {"session": SID, "text": "hello", "device": "desktop"}


def test_polish_ids_pass_and_nfd_ids_fail() -> None:
    ok = protocol.validate(RID, req("session_start", subject="łódź", card="pojęcia"))
    assert ok.body["subject"] == "łódź"
    assert ok.body["card"] == "pojęcia"
    for bad in ("zażółć", "Łódź", "ą" * 49):
        assert code_of(req("session_start", subject=bad, card=None)) == "bad_request"


def test_every_kind_has_a_lane_and_validates() -> None:
    bodies = {
        "subject_new": {"text": "cars"},
        "plan_revise": {"subject": "car", "plan_rev": 3, "comment": "less"},
        "plan_edit": {"subject": "car", "plan_rev": 3, "modules": [{"id": "a"}]},
        "plan_approve": {"subject": "car", "plan_rev": 4},
        "subject_finish": {"subject": "car", "choice": "go_deeper"},
        "module_pregenerate": {"subject": "car", "modules": "all"},
        "card_edit": {
            "subject": "car",
            "card": None,
            "module": "engine",
            "front": "f",
            "back": "b",
            "source": "https://x",
            "excerpt": "e",
            "requires": ["a-b"],
        },
        "session_start": {"subject": None, "card": None},
        "session_resume": {"session": SID},
        "next": {"session": SID},
        "stop": {"session": SID},
        "card_done": {"subject": "automation", "card": "ld-x", "done": False},
    }
    for kind, body in bodies.items():
        assert isinstance(body, dict)
        got = protocol.validate(RID, req(kind, **body))
        assert got.lane == protocol.KINDS[kind][0]
    no_sent = req()
    del no_sent["sent_at"]
    assert protocol.validate(RID, no_sent).sent_at_ms is None


@pytest.mark.parametrize(
    "raw",
    [
        "x",
        req("bogus"),
        {**req(), "dev": "pc"},
        {**req(), "created": {".sv": "timestamp"}},
        {**req(), "created": True},
        {**req(), "sent_at": -1},
        req(session="../etc", text="x"),
        req(session=SID, text="   "),
        req(session=SID, text="x" * 8001),
        req("session_start", subject="Car", card=None),
        req("session_start", subject=None, card="a" * 49),
        req("plan_approve", subject="car", plan_rev=False),
        req("subject_finish", subject="car", choice="later"),
        req("card_edit", subject="car", card=None, module="m", front=1),
        req("plan_edit", subject="car", plan_rev=1, modules=["x"]),
        req(
            "card_edit",
            subject="c",
            module="m",
            front="",
            back="",
            source="",
            excerpt="",
            requires="a",
        ),
        req("card_done", subject=None, card="ld-x", done="yes"),
        {**req(), "body": {"session": SID, "text": "y" * 39_000}, "pad": "z" * 2000},
    ],
)
def test_bad_requests(raw: object) -> None:
    assert code_of(raw) == "bad_request"


def test_body_not_a_dict_is_missing_fields() -> None:
    assert code_of({**req(), "body": "nope"}) == "bad_request"


def test_rid_check() -> None:
    assert protocol.valid_rid(RID)
    assert not protocol.valid_rid("01M4RBCX52MMHCK7K73E6KV90U")  # U is not Crockford
    assert not protocol.valid_rid("abc")


class CodedError(Exception):
    def __init__(self) -> None:
        super().__init__("curriculum says no")
        self.code = "plan_conflict"


def test_classify() -> None:
    own = RequestError("x", code="locked")
    assert classify(own) is own
    assert RequestError("x", code="nonsense").code == "worker_error"
    theirs = classify(CodedError())
    assert (theirs.code, theirs.message, theirs.retry) == (
        "plan_conflict",
        "curriculum says no",
        False,
    )
    for err in (SessionError("cli died"), ClaudeSDKError("x"), TimeoutError()):
        got = classify(err)
        assert (got.code, got.retry) == ("model_error", True)
    assert (
        classify(ValueError("cannot mark done 'x': locked until a are done")).code
        == "locked"
    )
    assert classify(ValueError("unknown card 'zz'")).code == "unknown_card"
    assert classify(ValueError("no unfinished card left")).code == "no_card_left"
    assert classify(ValueError("weird")).code == "bad_request"
    assert classify(RuntimeError("no session started")).code == "not_live"
    assert classify(RuntimeError("other")).code == "worker_error"
    assert classify(KeyError("k")).message == "worker error: KeyError"
    assert result_of(RequestError("m", code="gave_up")) == {
        "ok": False,
        "code": "gave_up",
        "error": "m",
        "retry": False,
    }
    assert "gave_up" in errors.CODES


def test_curriculum_error_fields_reach_the_result() -> None:
    extra = {"subject_title": "Cars", "next": "reviews_due", "due_at": 5}
    got = classify(CurriculumError("no_card_left", "Cars — x", extra=extra))
    assert result_of(got) == {
        **extra,
        "ok": False,
        "code": "no_card_left",
        "error": "Cars — x",
        "retry": False,
    }


def test_done_map_records_prunes_and_survives_bad_lines(tmp_path: Path) -> None:
    path = tmp_path / "d" / "requests_done.jsonl"
    done = DoneMap(path, now=1000.0)
    assert done.get(RID) is None
    done.add(RID, 1000.0, DEV, "message", {"ok": True, "data": {}})
    done.add("OLD", 1.0, "", "stop", {"ok": True})
    assert (done.get(RID) or {})["kind"] == "message"
    assert done.dev_of(RID) == DEV
    assert done.dev_of("OLD") is None
    assert done.dev_of("nope") is None
    with path.open("a") as handle:
        handle.write("not json\n")
        handle.write(json.dumps({"rid": "X"}) + "\n")
    again = DoneMap(path, now=KEEP_S + 500.0)
    assert again.get(RID) is not None
    assert again.get("OLD") is None
    assert len(path.read_text().splitlines()) == 1
    untouched = DoneMap(path, now=KEEP_S + 500.0)
    assert untouched.get(RID) is not None


def test_card_edit_requires_absent_is_empty() -> None:
    # RTDB stores no empty arrays: a card with no prerequisites arrives without
    # ``requires`` at all, and must still be editable from the phone.
    body = {
        "subject": "car",
        "card": "c",
        "module": "engine",
        "front": "f",
        "back": "b",
        "source": "https://x",
        "excerpt": "e",
    }
    got = protocol.validate(RID, req("card_edit", **body))
    assert got.body["requires"] == []
