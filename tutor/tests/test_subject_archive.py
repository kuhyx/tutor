# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Archived subjects: hidden, never scheduled, unlearned, and restorable."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from tutor import __main__ as tutor_main
from tutor.curriculum import archive, plan_ops, regen
from tutor.curriculum.advance import fold_and_advance, pending
from tutor.curriculum.archive import subject_event
from tutor.curriculum.errors import RequestError
from tutor.curriculum.eventlog import ARCHIVE, UNARCHIVE, archived_subjects, parse
from tutor.curriculum.fold import fold
from tutor.curriculum.source import SubjectSource
from tutor.curriculum.stats import stats
from tutor.store import Store
from tutor.tests._cur import T0, D, card, make_ctx, module, review, subject, taught
from tutor.tests.test_planner import plan_reply

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.curriculum.context import Context

EID = "01M4RBCX52MMHCK7K73E6KV910"


def _car(ctx: Context) -> None:
    """``car`` (a1 taught and reviewed Good) and ``bike`` (untouched)."""
    found = {"a1": card("a", 1), "a2": card("a", 2)}
    subject(
        ctx, "car", modules=[module("a", status="ready"), module("b", "a")], found=found
    )
    subject(ctx, "bike", found={"a1": card("a", 1)})
    taught(ctx, "car", "a1", T0)
    review(ctx, "car", "a1", T0 + D, 3)


def _files(ctx: Context, name: str) -> dict[str, bytes]:
    where = ctx.subjects.dir(name)
    return {p.name: p.read_bytes() for p in sorted(where.iterdir())}


def test_archive_appends_one_event_and_leaves_files_alone(tmp_path: Path) -> None:
    ctx, fakes = make_ctx(tmp_path)
    _car(ctx)
    log_before, files = ctx.log.path.read_bytes(), _files(ctx, "car")
    fakes.now[0] = T0 + 2 * D
    assert archive.subject_archive({"subject": "car"}, ctx) == {
        "subject": "car",
        "archived": True,
    }
    after = ctx.log.path.read_bytes()
    assert after.startswith(log_before)  # append-only: history byte-identical
    assert len(after.splitlines()) == len(log_before.splitlines()) + 1
    event = ctx.log.read()[-1]
    assert (event["k"], event["s"], event["dev"], event["at"]) == (
        ARCHIVE,
        "car",
        "dev-pc",
        T0 + 2 * D,
    )
    assert "c" not in event
    assert _files(ctx, "car") == files
    assert ctx.subjects.subjects() == ["bike"]
    assert ctx.subjects.subjects(archived=True) == ["bike", "car"]
    assert ctx.archived() == {"car"}
    # Again: nothing new (idempotent).
    assert archive.subject_archive({"subject": "car"}, ctx)["archived"] is True
    assert ctx.log.path.read_bytes() == after


def test_archive_refuses_unknown_and_bad_ids(tmp_path: Path) -> None:
    ctx, _ = make_ctx(tmp_path)
    for body in ({"subject": "nope"}, {"subject": "Bad Id"}, {}):
        with pytest.raises(RequestError) as err:
            archive.subject_archive(body, ctx)
        assert err.value.code == "bad_request"
    assert not ctx.log.path.exists()


def test_archive_unlearns_and_unarchive_restores_exactly(tmp_path: Path) -> None:
    ctx, fakes = make_ctx(tmp_path)
    _car(ctx)
    before = ctx.fold().card("car", "a1")
    assert before.taught
    assert before.app_good
    state = before.fsrs_state()
    assert stats(ctx, {})["days"]
    fakes.now[0] = T0 + 2 * D
    archive.subject_archive({"subject": "car"}, ctx)
    folded = ctx.fold()
    assert not folded.card("car", "a1").taught
    assert folded.card("car", "a1").fsrs_state() is None
    assert folded.taught_ids("car") == set()
    assert all(e.get("s") != "car" for e in folded.kept)
    assert stats(ctx, {})["days"] == {}  # nothing of it counts as learned or reviewed
    fakes.now[0] = T0 + 3 * D
    assert archive.subject_unarchive({"subject": "car"}, ctx) == {
        "subject": "car",
        "archived": False,
    }
    back = ctx.fold().card("car", "a1")
    assert back.taught
    assert back.app_good
    assert back.fsrs_state() == state
    assert ctx.subjects.subjects() == ["bike", "car"]
    # Not archived: unarchive again writes nothing.
    size = ctx.log.path.stat().st_size
    archive.subject_unarchive({"subject": "car"}, ctx)
    assert ctx.log.path.stat().st_size == size


def test_the_shared_fold_skips_subject_events(tmp_path: Path) -> None:
    ctx, _ = make_ctx(tmp_path)
    _car(ctx)
    events = [*ctx.log.read(), subject_event(ARCHIVE, "car", dev="dev-pc", at=T0 + D)]
    assert fold(events).card("car", "a1").taught  # the mask is the PC's, not here
    assert archived_subjects(events) == {"car"}


def test_latest_archive_event_wins_by_at_then_eid() -> None:
    late = subject_event(UNARCHIVE, "car", dev="pc", at=T0 + 5)
    early = subject_event(ARCHIVE, "car", dev="pc", at=T0)
    other = subject_event(ARCHIVE, "bike", dev="pc", at=T0)
    assert archived_subjects([late, early, other]) == {"bike"}


@pytest.mark.parametrize(
    "raw",
    [
        {"k": ARCHIVE, "at": T0},
        {"k": UNARCHIVE, "s": "Bad Id", "at": T0},
        {"k": ARCHIVE, "s": 3, "at": T0},
    ],
)
def test_parse_drops_malformed_subject_events(raw: dict[str, Any]) -> None:
    assert parse("pc", EID, raw) is None


def test_parse_keeps_subject_events_without_extra_keys() -> None:
    raw = {"k": ARCHIVE, "s": "car", "c": "x", "at": T0, "junk": 1}
    assert parse("pc", EID, raw) == {
        "dev": "pc",
        "eid": EID,
        "k": ARCHIVE,
        "s": "car",
        "at": T0,
    }


def test_archived_subject_is_never_advanced_or_generated(tmp_path: Path) -> None:
    ctx, _ = make_ctx(tmp_path)
    _car(ctx)
    archive.subject_archive({"subject": "car"}, ctx)
    files = _files(ctx, "car")
    review(ctx, "car", "a2", T0 + D, 3)  # a stray phone review after archiving
    assert fold_and_advance(ctx) == {"changed": [], "generate": []}
    assert pending(ctx) == []
    assert _files(ctx, "car") == files


def test_archived_subject_has_no_card_to_teach(tmp_path: Path) -> None:
    ctx, _ = make_ctx(tmp_path)
    _car(ctx)
    archive.subject_archive({"subject": "car"}, ctx)
    src = SubjectSource(Store(tmp_path), ctx, "car")
    with pytest.raises(RequestError) as err:
        src.pick(None)
    assert err.value.code == "no_card_left"
    assert err.value.extra["next"] == "none"
    assert err.value.extra["subject_id"] == "car"
    with pytest.raises(RequestError):
        src.pick("a2")


def test_same_title_after_archive_starts_fresh(tmp_path: Path) -> None:
    ctx, fakes = make_ctx(tmp_path)
    text = "I want to learn how a car works"
    fakes.replies = [plan_reply("a", "b", "c"), plan_reply("a", "b", "c")]
    assert plan_ops.subject_new({"text": text}, ctx) == {"subject": "how-a-car-works"}
    archive.subject_archive({"subject": "how-a-car-works"}, ctx)
    assert plan_ops.subject_new({"text": text}, ctx) == {"subject": "how-a-car-works-2"}
    assert ctx.subjects.subjects() == ["how-a-car-works-2"]
    assert ctx.archived() == {"how-a-car-works"}


def test_a_failed_archived_subject_is_not_reused(tmp_path: Path) -> None:
    ctx, fakes = make_ctx(tmp_path)
    fakes.replies = [RequestError("model_error", "down"), plan_reply("a", "b", "c")]
    with pytest.raises(RequestError):
        plan_ops.subject_new({"text": "tides"}, ctx)
    archive.subject_archive({"subject": "tides"}, ctx)
    assert plan_ops.subject_new({"text": "tides"}, ctx) == {"subject": "tides-2"}
    assert ctx.subjects.need_meta("tides").status == "failed"


def test_cli_archives_and_unarchives(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ctx, _ = make_ctx(tmp_path)
    _car(ctx)
    (tmp_path / "device_id").write_text("dev-pc\n")
    data = ["--data", str(tmp_path)]
    assert tutor_main.main(["subject", "archive", "car", *data]) == 0
    assert '"archived": true' in capsys.readouterr().out
    assert ctx.archived() == {"car"}
    assert ctx.log.read()[-1]["dev"] == "dev-pc"
    assert tutor_main.main(["subject", "unarchive", "car", *data]) == 0
    assert ctx.archived() == set()
    assert tutor_main.main(["subject", "archive", "nope", *data]) == 2
    assert "refused: unknown subject" in capsys.readouterr().out


def test_regenerate_refuses_an_archived_subject(tmp_path: Path) -> None:
    # Its masked fold has no taught cards: a repair would judge them all.
    ctx, _ = make_ctx(tmp_path)
    _car(ctx)
    archive.subject_archive({"subject": "car"}, ctx)
    with pytest.raises(RequestError) as err:
        regen.regenerate(ctx, "car", "a")
    assert err.value.code == "bad_request"
    assert "archived" in err.value.message
