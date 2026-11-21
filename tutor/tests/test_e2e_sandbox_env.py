# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The e2e sandbox server keeps its faults off kuhy's real app-errors board.

F14 and the C12 live check start the sandbox server with every model call
failing on purpose. The server files model faults to
``$XDG_STATE_HOME/app-errors-spool`` (``tutor.model_fault``); when the unit
inherited the real state dir, those staged failures reached the board as fix
tasks (tutor:66e50650e7, tutor:89b8b49e07, 2026-11-21). ``start_server`` must
point ``XDG_STATE_HOME`` into the sandbox.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess

HELPER = Path(__file__).resolve().parents[2] / "scripts" / "_e2e_sandbox_units.sh"

# Records its argv; curl answers "up" to every probe so the waits end at once.
FAKE_SYSTEMD_RUN = '#!/bin/bash\nprintf "%s\\n" "$@" >>"$FAKE_LOG"\n'
FAKE_CURL = "#!/bin/bash\necho '{}'\n"
FAKE_SYSTEMCTL = "#!/bin/bash\nexit 0\n"


def _exe(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def _server_argv(tmp_path: Path) -> list[str]:
    """Run ``start_server`` against fakes; return the systemd-run argv lines."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _exe(bin_dir / "systemd-run", FAKE_SYSTEMD_RUN)
    _exe(bin_dir / "curl", FAKE_CURL)
    _exe(bin_dir / "systemctl", FAKE_SYSTEMCTL)
    sandbox = tmp_path / "sandbox"
    state = tmp_path / "state.env"
    state.write_text(
        f"SANDBOX={sandbox}\nDB=http://127.0.0.1:1\nPORT=2\nDEV=d\nCLOCK=\nMODEL=\n",
        encoding="utf-8",
    )
    log = tmp_path / "argv.log"
    script = (
        "set -euo pipefail\n"
        'die() { echo "$*" >&2; exit 1; }\n'
        f'ROOT=/r PY=/py WEB=/w SUBJECT=s FOCUS_SRC=/f STATE="{state}"\n'
        "SERVER_UNIT=srv MODEL_UNIT=mdl\n"
        f'source "{HELPER}"\n'
        "start_server\n"
    )
    env = {**os.environ, "PATH": f"{bin_dir}:/usr/bin:/bin", "FAKE_LOG": str(log)}
    subprocess.run(["/usr/bin/bash", "-c", script], check=True, env=env, timeout=20)
    return log.read_text(encoding="utf-8").splitlines()


def test_server_state_dir_is_inside_the_sandbox(tmp_path: Path) -> None:
    """The unit gets ``XDG_STATE_HOME=<sandbox>/state``, never the real one."""
    argv = _server_argv(tmp_path)
    states = [a for a in argv if a.startswith("XDG_STATE_HOME=")]
    assert states == [f"XDG_STATE_HOME={tmp_path / 'sandbox' / 'state'}"]
