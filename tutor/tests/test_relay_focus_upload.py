# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The rules screenshot travels as chunks in ``uploads/{ulid}``, not in the request."""

from __future__ import annotations

import base64
import hashlib
import logging
from typing import TYPE_CHECKING, Any

import pytest

from tutor.relay.errors import RequestError
from tutor.store import data_dir
from tutor.tests._fake_rtdb import FakeRtdb
from tutor.tests._interview_support import call, install, interview_project

if TYPE_CHECKING:
    from tutor.tests._fake_fp_interview import FakeInterviewFp

ULID = "01J00000000000000000000001"
PNG = b"\x89PNG\r\n\x1a\n" + b"rules screenshot" * 40
JPEG = b"\xff\xd8\xff\xe0" + b"jpeg" * 40
WEBP = b"RIFF\x24\x00\x00\x00WEBP" + b"webp" * 40


def put(
    fake: FakeRtdb, raw: bytes, *, size: int = 100, upload: str = ULID
) -> dict[str, Any]:
    """Write ``raw`` as chunks of ``size`` b64 chars; returns the request body."""
    text = base64.b64encode(raw).decode()
    parts = [text[i : i + size] for i in range(0, len(text), size)]
    node = {f"c{n:04d}": part for n, part in enumerate(parts, start=1)}
    fake.set(f"tutor/v1/uploads/{upload}", node)
    return {
        "id": "codility",
        "milestone": "rules",
        "kind": "file",
        "upload": upload,
        "chunks": len(parts),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "mime": "image/png",
    }


@pytest.fixture
def fp(monkeypatch: pytest.MonkeyPatch) -> FakeInterviewFp:
    fake = install(monkeypatch)
    interview_project(fake)
    return fake


def refused(body: dict[str, Any], fake: FakeRtdb) -> RequestError:
    with pytest.raises(RequestError) as caught:
        call("focus_evidence", body, fake)
    return caught.value


def test_a_png_upload_becomes_the_rules_file_and_is_cleaned_up(
    fp: FakeInterviewFp,
) -> None:
    fake = FakeRtdb()
    body = put(fake, PNG)
    assert body["chunks"] > 1
    got = call("focus_evidence", body, fake)
    assert got["missed"] is False
    args = next(a for n, a in fp.calls if n == "record_evidence")
    assert args["kind"] == "file"
    assert args["milestone"] == "rules"
    name, data = args["file"]
    assert name.endswith(".png")
    assert data == PNG
    assert fake.get(f"tutor/v1/uploads/{ULID}") is None
    assert not list(data_dir().rglob("*.png"))  # the temp copy is gone


@pytest.mark.parametrize(
    ("raw", "mime", "suffix"),
    [(JPEG, "image/jpeg", ".jpg"), (WEBP, "image/webp", ".webp")],
)
def test_jpeg_and_webp_are_accepted(
    fp: FakeInterviewFp, raw: bytes, mime: str, suffix: str
) -> None:
    fake = FakeRtdb()
    call("focus_evidence", put(fake, raw) | {"mime": mime}, fake)
    name, _ = next(a for n, a in fp.calls if n == "record_evidence")["file"]
    assert name.endswith(suffix)


@pytest.mark.parametrize(
    "damage",
    [
        "sha",
        "base64",
        "missing_chunk",
        "chunk_not_text",
        "chunk_too_long",
        "mime_mismatch",
        "not_an_image",
        "no_upload",
        "node_not_a_dict",
    ],
)
def test_a_bad_upload_is_refused_and_still_deleted(
    fp: FakeInterviewFp, damage: str
) -> None:
    fake = FakeRtdb()
    body = put(fake, PNG)
    path = f"tutor/v1/uploads/{ULID}"
    if damage == "sha":
        body["sha256"] = "0" * 64
    elif damage == "base64":
        fake.set(f"{path}/c0001", "!!!!")
    elif damage == "missing_chunk":
        body["chunks"] += 1
    elif damage == "chunk_not_text":
        fake.set(f"{path}/c0001", 5)
    elif damage == "chunk_too_long":
        fake.set(f"{path}/c0001", "A" * 300_000)
    elif damage == "mime_mismatch":
        body["mime"] = "image/jpeg"
    elif damage == "not_an_image":
        body = put(fake, b"just text, not an image" * 10)
    elif damage == "no_upload":
        fake.set(path, None)
    else:
        fake.set(path, "oops")
    assert refused(body, fake).code == "bad_request"
    assert fake.get(path) is None
    assert not [c for c in fp.calls if c[0] == "record_evidence"]


@pytest.mark.parametrize("missing", ["upload", "chunks", "sha256", "mime"])
def test_a_file_kind_needs_all_its_upload_fields(
    fp: FakeInterviewFp, missing: str
) -> None:
    fake = FakeRtdb()
    body = put(fake, PNG)
    del body[missing]
    assert refused(body, fake).code == "bad_request"
    assert not fp.calls


def test_the_registry_refusing_a_file_is_loud_and_cleans_up(
    fp: FakeInterviewFp,
) -> None:
    fake = FakeRtdb()
    body = put(fake, PNG)
    fp.refuse = ValueError("'rules' is not a milestone")
    got = refused(body, fake)
    assert got.code == "focus_refused"
    assert fake.get(f"tutor/v1/uploads/{ULID}") is None


def test_an_unreadable_database_is_a_retryable_error(fp: FakeInterviewFp) -> None:
    fake = FakeRtdb()
    body = put(fake, PNG)
    fake.fail[("GET", f"/uploads/{ULID}")] = 503
    got = refused(body, fake)
    assert (got.code, got.retry) == ("worker_error", True)
    assert not fp.calls


def test_a_failed_delete_is_logged_not_raised(
    fp: FakeInterviewFp, caplog: pytest.LogCaptureFixture
) -> None:
    fake = FakeRtdb()
    body = put(fake, PNG)
    fake.fail[("DELETE", f"/uploads/{ULID}")] = 500
    with caplog.at_level(logging.WARNING):
        call("focus_evidence", body, fake)
    assert "upload" in caplog.text
    assert any(n == "record_evidence" for n, _ in fp.calls)
