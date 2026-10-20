# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``scripts/tutor_model_sandbox.sh`` under a real bubblewrap, bash as the "CLI".

What the model's process can and cannot see: the scratch HOME yes; the data
dir, the ledger key, the rest of HOME, the repo and TUTOR_* no.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile

import pytest

from tutor import research

BWRAP = shutil.which("bwrap")


def _bwrap_works() -> bool:
    """The wrapper runs ``true`` (no bwrap, or no user namespaces: skip)."""
    if BWRAP is None:
        return False
    with tempfile.TemporaryDirectory() as box:
        env = {
            **os.environ,
            "TUTOR_MODEL_SANDBOX": box,
            "TUTOR_MODEL_CLI": "/usr/bin/true",
        }
        run = subprocess.run(
            [str(research.WRAPPER)], env=env, check=False, capture_output=True
        )
    return run.returncode == 0


pytestmark = pytest.mark.skipif(not _bwrap_works(), reason="no usable bwrap")


def inside(root: Path, script: str) -> subprocess.CompletedProcess[str]:
    """Run ``bash -c script`` through the wrapper, as the SDK would run the CLI."""
    env = {
        **os.environ,
        "TUTOR_MODEL_SANDBOX": str(root),
        "TUTOR_MODEL_CLI": "/usr/bin/bash",
        "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
        "SSH_AUTH_SOCK": "/run/user/1000/ssh-agent.sock",
    }
    return subprocess.run(
        [str(research.WRAPPER), "-c", script],
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )


@pytest.fixture
def root(tutor_sandbox: Path) -> Path:
    found = research.sandbox_root()
    (found / "home").mkdir(parents=True)
    return found


def test_the_cli_sees_its_scratch_home_and_a_fresh_work_dir(root: Path) -> None:
    run = inside(root, 'echo "$HOME|$PWD"; touch "$HOME/kept" "$PWD/scratch"')
    assert run.returncode == 0, run.stderr
    home, work = run.stdout.strip().split("|")
    assert home == str(root / "home")
    assert Path(work).parent == root / "home" / "work"
    assert (root / "home" / "kept").is_file()  # installs persist in HOME
    assert (Path(work) / "scratch").is_file()


def test_private_paths_are_invisible(tutor_sandbox: Path, root: Path) -> None:
    data = tutor_sandbox / "data"
    (data / "ledger.json").write_text("{}", encoding="utf-8")
    secret = tutor_sandbox / "home" / ".claude" / "rules" / "secret.md"
    secret.parent.mkdir(parents=True)
    secret.write_text("x", encoding="utf-8")
    probes = [
        data / "ledger.json",  # the data dir (TUTOR_DATA)
        tutor_sandbox / "hmac.key",  # the ledger key (TUTOR_KEY)
        Path("/etc/workout-locker/hmac.key"),  # the real ledger key
        secret,  # kuhy's ~/.claude
        research.WRAPPER.parent.parent / "tutor" / "credit.py",  # the repo
    ]
    checks = " ".join(f'test -e "{p}" && echo "SEEN {p}";' for p in probes)
    run = inside(root, checks + " true")
    assert run.returncode == 0, run.stderr
    assert "SEEN" not in run.stdout


def test_host_services_are_unreachable(root: Path) -> None:
    """No route back to the host: its loopback (the tutor's :8778 API, which
    mints credit) and its abstract unix sockets (the X server)."""
    tcp = socket.socket()
    tcp.bind(("127.0.0.1", 0))
    tcp.listen()
    port = tcp.getsockname()[1]
    abstract = socket.socket(socket.AF_UNIX)
    name = f"tutor-sandbox-test-{os.getpid()}"
    abstract.bind("\0" + name)
    abstract.listen()
    script = (
        "import socket\n"
        "for family, address in ("
        f"(socket.AF_INET, ('127.0.0.1', {port})), "
        f"(socket.AF_UNIX, '\\0{name}')):\n"
        "    s = socket.socket(family)\n"
        "    s.settimeout(3)\n"
        "    try:\n"
        "        s.connect(address)\n"
        "        print('REACHED', address)\n"
        "    except OSError as err:\n"
        "        print('refused', address, err)\n"
    )
    with tcp, abstract:
        run = inside(root, f'python3 -c "{script}"')
    assert run.returncode == 0, run.stderr
    assert "REACHED" not in run.stdout
    assert sum(ln.startswith("refused ") for ln in run.stdout.splitlines()) == 2


def test_the_environment_is_an_allowlist(root: Path) -> None:
    run = inside(root, "env")
    assert run.returncode == 0, run.stderr
    names = {line.split("=", 1)[0] for line in run.stdout.splitlines()}
    assert not {n for n in names if n.startswith("TUTOR_")}
    assert "SSH_AUTH_SOCK" not in names
    assert "CLAUDE_CODE_DISABLE_AUTO_MEMORY" in names
    assert "PATH" in names


def test_missing_settings_are_refused(tutor_sandbox: Path) -> None:
    env = {k: v for k, v in os.environ.items() if not k.startswith("TUTOR_MODEL")}
    run = subprocess.run(
        [str(research.WRAPPER), "-v"],
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert run.returncode != 0
    assert "TUTOR_MODEL_SANDBOX" in run.stderr
