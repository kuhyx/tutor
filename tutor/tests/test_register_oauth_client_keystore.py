# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""scripts/register_oauth_client.sh: which keystore it reads, and refusing a foreign one.

Same rig as ``test_register_oauth_client.py`` (``_register_oauth_support``).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tutor.tests import _register_oauth_support as support

rig = support.rig
_run = support.run
_firebase_log = support.firebase_log
_key_props = support.key_props
APP_SHA1 = support.APP_SHA1
HOME_SHA1 = support.HOME_SHA1


def test_sha1_prefers_the_repo_key_properties(rig: dict[str, Path]) -> None:
    home_only = _run(rig, "--sha1")
    _key_props(rig["repo"] / "app" / "android", "app.jks", APP_SHA1)
    repo_first = _run(rig, "--sha1")
    assert home_only.stdout.strip() == HOME_SHA1
    assert repo_first.stdout.strip() == APP_SHA1
    # The password goes through the environment, never argv.
    assert "secretpw" not in (rig["state"] / "keytool.log").read_text()


def test_no_key_properties_anywhere_is_an_error(rig: dict[str, Path]) -> None:
    (Path(os.environ["HOME"]) / ".android" / "release" / "key.properties").unlink()
    result = _run(rig, "--sha1")
    assert result.returncode == 1
    assert "key.properties" in result.stderr


@pytest.mark.parametrize("args", [[], ["--check"], ["--sha1"]])
def test_a_foreign_keystore_is_refused_before_any_firebase_write(
    rig: dict[str, Path], args: list[str]
) -> None:
    result = _run(rig, *args, env={"FAKE_SHA256": "00:11"})
    assert result.returncode == 1
    assert "not the shared kuhy key" in result.stderr
    assert "create" not in _firebase_log(rig)
