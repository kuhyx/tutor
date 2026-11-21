# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Shared rig for the scripts/register_oauth_client.sh tests.

Fake firebase, keytool and adb, a temp repo holding a copy of the script,
and a home keystore. Test modules bind the ``rig`` fixture by assignment
(``rig = support.rig``).
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


def write_exe(path: Path, body: str) -> None:
    path.write_text(body)
    path.chmod(0o755)


def key_props(directory: Path, store: str, sha1: str) -> None:
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
    for helper in SCRIPT.parent.glob("_register_oauth_client*.sh"):
        shutil.copy(helper, repo / "scripts" / helper.name)
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
        write_exe(fakebin / name, body)
    state = tmp_path / "state"
    state.mkdir()
    key_props(Path(os.environ["HOME"]) / ".android" / "release", "home.jks", HOME_SHA1)
    return {"repo": repo, "fakebin": fakebin, "state": state}


def run(
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


def firebase_log(rig: dict[str, Path]) -> str:
    log = rig["state"] / "firebase.log"
    return log.read_text() if log.exists() else ""
