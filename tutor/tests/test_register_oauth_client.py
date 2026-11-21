# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""scripts/register_oauth_client.sh against a fake firebase, keytool and adb.

The script is copied into a temp repo so ``app/android/key.properties`` is a
temp file too; HOME is already private (conftest), so the
``~/.android/release`` fallback is a temp file as well. Nothing here reaches
the real Firebase project or the phone.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tutor.tests import _register_oauth_support as support

rig = support.rig
_run = support.run
_firebase_log = support.firebase_log
APP_ID = support.APP_ID
HOME_HEX = support.HOME_HEX
HOME_SHA1 = support.HOME_SHA1
SCRIPT = support.SCRIPT

if TYPE_CHECKING:
    from pathlib import Path


def test_header_no_longer_claims_the_cli_cannot_create_the_client() -> None:
    header = SCRIPT.read_text().split("set -euo pipefail")[0]
    assert "no create API" not in header
    assert "Firebase CLI has no" not in header
    assert "apps:android:sha:create" in header


def test_missing_app_and_sha_are_both_created(rig: dict[str, Path]) -> None:
    result = _run(rig)
    log = _firebase_log(rig)
    assert "apps:create ANDROID tutor --package-name com.kuhy.tutor" in log
    assert f"apps:android:sha:create {APP_ID} {HOME_HEX}" in log
    assert f"com.kuhy.tutor registered as {APP_ID}" in result.stdout
    # Registration done, then the phone check: no phone attached here.
    assert "phone not attached" in result.stdout
    assert result.returncode == 1


def test_only_the_missing_sha_is_created(rig: dict[str, Path]) -> None:
    (rig["state"] / "app").touch()
    _run(rig)
    log = _firebase_log(rig)
    assert "apps:create" not in log
    assert f"apps:android:sha:create {APP_ID} {HOME_HEX}" in log


def test_registered_app_and_sha_create_nothing(rig: dict[str, Path]) -> None:
    (rig["state"] / "app").touch()
    (rig["state"] / "sha").write_text(HOME_HEX.upper())
    result = _run(rig)
    assert "create" not in _firebase_log(rig)
    assert f"com.kuhy.tutor registered as {APP_ID}" in result.stdout


def test_check_passes_when_both_are_registered(rig: dict[str, Path]) -> None:
    (rig["state"] / "app").touch()
    (rig["state"] / "sha").write_text(HOME_HEX)
    first = _run(rig, "--check")
    second = _run(rig, "--check")
    assert (first.returncode, second.returncode) == (0, 0)
    assert "create" not in _firebase_log(rig)


@pytest.mark.parametrize("present", [[], ["app"]])
def test_check_fails_when_something_is_missing(
    rig: dict[str, Path], present: list[str]
) -> None:
    for name in present:
        (rig["state"] / name).touch()
    result = _run(rig, "--check")
    assert result.returncode == 1
    assert "not registered" in result.stderr
    assert "create" not in _firebase_log(rig)


@pytest.mark.parametrize(
    ("uninstall", "reason"), [(True, "not installed"), (False, "not logged in")]
)
def test_no_usable_cli_falls_back_to_the_console(
    rig: dict[str, Path], uninstall: bool, reason: str
) -> None:
    if uninstall:
        (rig["fakebin"] / "firebase").unlink()
    result = _run(rig, env={"FAKE_LOGGED_OUT": "1"})
    assert reason in result.stdout
    assert "CREATE CLIENT" in result.stdout
    assert HOME_SHA1 in result.stdout
    assert "create" not in _firebase_log(rig)


@pytest.mark.parametrize("uninstall", [True, False])
def test_check_never_falls_back(rig: dict[str, Path], uninstall: bool) -> None:
    if uninstall:
        (rig["fakebin"] / "firebase").unlink()
    result = _run(rig, "--check", env={"FAKE_LOGGED_OUT": "1"})
    assert result.returncode == 1
    assert "CREATE CLIENT" not in result.stdout


def test_a_failed_sha_create_reports_firebase_s_reason(rig: dict[str, Path]) -> None:
    (rig["state"] / "app").touch()
    result = _run(rig, env={"FAKE_SHA_FAIL": "1"})
    assert result.returncode == 1
    assert "already in use" in result.stderr


@pytest.mark.parametrize(
    ("label", "rc", "verdict"),
    [
        ("New subject", 0, "SIGNED IN: the Home screen"),
        ("Sign in with Google", 1, "NOT SIGNED IN"),
        ("Coach", 1, "Neither the sign-in nor the Home screen"),
    ],
)
def test_verify_only_reads_the_screen(
    rig: dict[str, Path], label: str, rc: int, verdict: str
) -> None:
    screen = f'<hierarchy><node content-desc="{label}" /></hierarchy>'
    result = _run(rig, "--verify-only", env={"FAKE_SCREEN": screen})
    assert result.returncode == rc
    assert verdict in result.stdout


def test_unknown_flag_prints_usage(rig: dict[str, Path]) -> None:
    result = _run(rig, "--bogus")
    assert result.returncode == 2
    assert "--check" in result.stderr
