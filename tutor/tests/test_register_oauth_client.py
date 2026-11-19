# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""scripts/register_oauth_client.sh against a fake firebase, keytool and adb.

The script is copied into a temp repo so ``app/android/key.properties`` is a
temp file too; HOME is already private (conftest), so the
``~/.android/release`` fallback is a temp file as well. Nothing here reaches
the real Firebase project or the phone.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "register_oauth_client.sh"
CANONICAL_SHA256 = (
    "9D:CC:2E:6C:05:3C:44:BB:05:07:90:3B:9D:D3:51:01:"
    "5E:A7:D4:31:5B:6E:E6:C8:53:DD:8D:80:7B:98:F8:46"
)
APP_SHA1 = "AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99:AA:BB:CC:DD"
HOME_SHA1 = "11:22:33:44:55:66:77:88:99:00:AA:BB:CC:DD:EE:FF:11:22:33:44"
HOME_HEX = HOME_SHA1.replace(":", "").lower()
APP_ID = "1:845446124781:android:fake"

# Answers like the real CLI: a notice line before the JSON, state in files.
FAKE_FIREBASE = """#!/bin/bash
echo "firebase $*" >>"$FAKE_STATE/firebase.log"
echo "i  fake notice"
case "$1" in
login:list)
    if [[ -n "${FAKE_LOGGED_OUT:-}" ]]; then echo '{"result":[]}'
    else echo '{"result":[{"user":{}}]}'; fi ;;
apps:list)
    if [[ -f "$FAKE_STATE/app" ]]; then
        echo '{"result":[{"packageName":"com.kuhy.tutor","appId":"'"$FAKE_APP_ID"'"}]}'
    else echo '{"result":[]}'; fi ;;
apps:create) touch "$FAKE_STATE/app"; echo '{"result":{}}' ;;
apps:android:sha:list)
    if [[ -f "$FAKE_STATE/sha" ]]; then
        echo '{"result":[{"shaHash":"'"$(cat "$FAKE_STATE/sha")"'"}]}'
    else echo '{"result":[]}'; fi ;;
apps:android:sha:create)
    if [[ -n "${FAKE_SHA_FAIL:-}" ]]; then
        echo "Error: SHA already in use by another OAuth client" >&2; exit 1
    fi
    echo "$3" >"$FAKE_STATE/sha"; echo '{"result":{}}' ;;
esac
"""

# The SHA-1 depends on which keystore was read, so the test sees which
# key.properties won.
FAKE_KEYTOOL = """#!/bin/bash
echo "keytool $*" >>"$FAKE_STATE/keytool.log"
store=""
while [[ $# -gt 0 ]]; do
    [[ "$1" == "-keystore" ]] && store="$2"
    shift
done
[[ -f "$store" ]] || exit 1
echo "Alias name: upload"
echo "Certificate fingerprints:"
echo "	 SHA1: $(cat "$store")"
echo "	 SHA256: ${FAKE_SHA256}"
"""

# No phone unless FAKE_SCREEN holds a screen dump; `pull` hands that back.
FAKE_ADB = """#!/bin/bash
if [[ "$1" == "devices" ]]; then
    echo "List of devices attached"
    [[ -z "${FAKE_SCREEN:-}" ]] || printf '23181JEGR08034\\tdevice\\n'
    exit 0
fi
[[ "$3" != "pull" ]] || printf '%s' "$FAKE_SCREEN" >"$5"
"""

# Exits at once: a background xdg-open must not eat the script's stdin.
NOOP = "#!/bin/bash\nexit 0\n"


def _write_exe(path: Path, body: str) -> None:
    path.write_text(body)
    path.chmod(0o755)


def _key_props(directory: Path, store: str, sha1: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / store).write_text(sha1)
    (directory / "key.properties").write_text(
        f"storePassword=secretpw\nkeyPassword=secretpw\nkeyAlias=upload\nstoreFile={store}\n"
    )


@pytest.fixture
def rig(tmp_path: Path) -> dict[str, Path]:
    """A temp repo holding the script, fake tools, a home keystore."""
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    shutil.copy(SCRIPT, repo / "scripts" / SCRIPT.name)
    fakebin = tmp_path / "fakebin"
    fakebin.mkdir()
    for name, body in {
        "firebase": FAKE_FIREBASE,
        "keytool": FAKE_KEYTOOL,
        "adb": FAKE_ADB,
        "xdg-open": NOOP,
        "xclip": NOOP,
        "sleep": NOOP,
    }.items():
        _write_exe(fakebin / name, body)
    state = tmp_path / "state"
    state.mkdir()
    _key_props(Path(os.environ["HOME"]) / ".android" / "release", "home.jks", HOME_SHA1)
    return {"repo": repo, "fakebin": fakebin, "state": state}


def _run(
    rig: dict[str, Path], *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    full_env = {
        "HOME": os.environ["HOME"],
        "PATH": f"{rig['fakebin']}:/usr/bin:/bin",
        "FAKE_STATE": str(rig["state"]),
        "FAKE_APP_ID": APP_ID,
        "FAKE_SHA256": CANONICAL_SHA256,
        **(env or {}),
    }
    return subprocess.run(
        ["/usr/bin/bash", str(rig["repo"] / "scripts" / SCRIPT.name), *args],
        env=full_env,
        input="\n" * 6,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def _firebase_log(rig: dict[str, Path]) -> str:
    log = rig["state"] / "firebase.log"
    return log.read_text() if log.exists() else ""


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
