#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Flow F32's scratch world: one case dir, its env, and the kinds of child.

A case is ``$E2E_PM_DIR/<case>/``: ``home/`` is the scratch ``$HOME`` of both
sides (tutor data ``home/.local/share/tutor`` is the guard's ``TUTOR_DIR``;
guard data ``home/.local/share/leetcode_guard`` is ``TUTOR_GUARD_DATA``),
``key`` the one scratch HMAC key both sign with, and a FAKE todo MCP server
(``e2e_pm_todo.py``) per case, a ``systemd-run --user`` unit. Children:
:meth:`Case.tutor` (this venv, ``e2e_pm_tutor.py``), :meth:`Case.guard` (the
system python in ``$E2E_GUARD_ROOT``), ``e2e_pm_seed.seed`` (private Xvfb).
Only :data:`LIVE_TUTOR` and :data:`LIVE_HISTORY` are read live, and copied.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import time
from typing import Any, Final

import e2e_pm_reply as canned

ROOT: Final = Path(__file__).resolve().parents[1]
BASE: Final = Path(os.environ.get("E2E_PM_DIR") or ROOT / "build/e2e-postmortem")
GUARD: Final = Path(
    os.environ.get("E2E_GUARD_ROOT") or Path.home() / "src/leetcode-guard"
)
LIVE_TUTOR: Final = Path.home() / ".local/share/tutor"
LIVE_HISTORY: Final = Path.home() / ".local/share/leetcode_guard/history"
TAG: Final = hashlib.sha256(str(ROOT).encode()).hexdigest()[:8]  # per worktree
SYSTEMD_RUN: Final = shutil.which("systemd-run") or "/usr/bin/systemd-run"
SYSTEMCTL: Final = shutil.which("systemctl") or "/usr/bin/systemctl"
UNIT_PREFIX: Final = f"tutor-e2e-pm-todo-{TAG}-"
PAST: Final = 1_795_370_367.0  # theory first done (2026-11-22): 3 solves before it


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@dataclass(frozen=True)
class Case:
    """One scratch case: its dirs, env and children."""

    name: str

    @property
    def dir(self) -> Path:
        """The case dir."""
        return BASE / self.name

    @property
    def home(self) -> Path:
        """The scratch ``$HOME`` of both sides."""
        return self.dir / "home"

    @property
    def data(self) -> Path:
        """The tutor's data dir."""
        return self.home / ".local/share/tutor"

    @property
    def guard_data(self) -> Path:
        """The guard's data dir."""
        return self.home / ".local/share/leetcode_guard"

    @property
    def unit(self) -> str:
        """The fake todo server's systemd unit."""
        return f"{UNIT_PREFIX}{self.name}"

    def tasks(self) -> list[dict[str, Any]]:
        """Every task the fake todo server received, in order."""
        path = self.dir / "todo_tasks.jsonl"
        lines = path.read_text("utf-8").splitlines() if path.is_file() else []
        return [json.loads(line)["args"] for line in lines]

    def create(self) -> None:
        """A fresh case dir, key and token; the fake todo server started."""
        self.stop()
        if self.dir.exists():
            shutil.rmtree(self.dir)
        for path in (self.data, self.guard_data / "history", self.home / "run"):
            path.mkdir(parents=True)
        (self.home / "run").chmod(0o700)
        (self.dir / "key").write_text(
            base64.b64encode(secrets.token_bytes(32)).decode() + "\n", "utf-8"
        )
        (self.dir / "todo_token").write_text(secrets.token_hex(16), "utf-8")
        port = _free_port()
        (self.dir / "todo_port").write_text(str(port), "utf-8")
        script = ROOT / "scripts/e2e_pm_todo.py"
        subprocess.run(
            [
                SYSTEMD_RUN,
                "--user",
                "--quiet",
                "--collect",
                f"--unit={self.unit}",
                "-p",
                "RuntimeMaxSec=7200",
                str(ROOT / ".venv/bin/python"),
                str(script),
                "--port",
                str(port),
                "--out",
                str(self.dir / "todo_tasks.jsonl"),
                "--token-file",
                str(self.dir / "todo_token"),
            ],
            check=True,
        )
        for _ in range(40):
            with socket.socket() as probe:
                if probe.connect_ex(("127.0.0.1", port)) == 0:
                    return
            time.sleep(0.25)
        msg = "fake todo server did not start"
        raise RuntimeError(msg)

    def stop(self) -> None:
        """Stop this case's fake todo server (if it runs)."""
        subprocess.run(
            [SYSTEMCTL, "--user", "stop", self.unit], check=False, capture_output=True
        )

    def tutor_env(self, *, model_down: bool = False) -> dict[str, str]:
        """Every tutor path in the case; todo at the fake; the model as asked."""
        port = (self.dir / "todo_port").read_text("utf-8").strip()
        env = {k: v for k, v in os.environ.items() if not k.startswith("TUTOR_")}
        env.pop("ANTHROPIC_BASE_URL", None)
        cache = self.dir / "cache"
        env |= {
            "E2E_PM_CASE": str(self.dir),
            "PYTHONPATH": f"{ROOT}:{ROOT / 'scripts'}",
            "TUTOR_DATA": str(self.data),
            "TUTOR_KEY": str(self.dir / "key"),
            "TUTOR_GUARD_DATA": str(self.guard_data),
            "TUTOR_THEORY_PHASE": str(self.guard_data / "theory_phase.json"),
            "TUTOR_SOURCE_CACHE": str(cache / "sources"),
            "TUTOR_IMAGE_CACHE": str(cache / "images"),
            "TUTOR_WIKI_CACHE": str(cache / "wiki"),
            "TUTOR_ANKI_COLLECTION": str(cache / "none.anki2"),
            "XDG_STATE_HOME": str(self.dir / "state"),
            "TUTOR_TODO_URL": f"http://127.0.0.1:{port}/mcp",
            "TUTOR_TODO_TOKEN_FILE": str(self.dir / "todo_token"),
        }
        if model_down:  # F14's outage: a closed port, no retry
            env |= {
                "ANTHROPIC_BASE_URL": "http://127.0.0.1:9",
                "CLAUDE_CODE_MAX_RETRIES": "0",
            }
        return env

    def tutor(self, *args: str, model_down: bool = False) -> dict[str, Any]:
        """Run one ``e2e_pm_tutor.py`` op; its JSON."""
        done = subprocess.run(
            [
                str(ROOT / ".venv/bin/python"),
                str(ROOT / "scripts/e2e_pm_tutor.py"),
                *args,
            ],
            env=self.tutor_env(model_down=model_down),
            capture_output=True,
            text=True,
            check=False,
            timeout=45,
            cwd=self.dir,
        )
        if done.returncode != 0:
            msg = f"tutor {args}: exit {done.returncode}\n{done.stderr[-3000:]}"
            raise RuntimeError(msg)
        return dict(json.loads(done.stdout.strip().splitlines()[-1]))

    def retry(self) -> str:
        """``python -m tutor postmortem prefix-sums --retry`` in the case env."""
        done = subprocess.run(
            [
                str(ROOT / ".venv/bin/python"),
                "-m",
                "tutor",
                "postmortem",
                "prefix-sums",
                "--retry",
            ],
            env=self.tutor_env(),
            capture_output=True,
            text=True,
            check=False,
            timeout=40,
            cwd=ROOT,
        )
        tail = done.stderr.strip()[-300:]
        return f"exit {done.returncode}: {done.stdout.strip()} {tail}"

    def guard_env(self, ac: str = "", display: str = "") -> dict[str, str]:
        """The guard role's env, as its own ``World.env``, under this case."""
        env = {k: v for k, v in os.environ.items() if k != "DISPLAY"}
        env |= {
            "HOME": str(self.home),
            "XDG_RUNTIME_DIR": str(self.home / "run"),
            "PYTHONUSERBASE": str(Path.home() / ".local"),
            "E2E_KEY": str(self.dir / "key"),
            "E2E_ROOT": str(GUARD),
            "E2E_MODEL": str(self.dir / "model.json"),
            "E2E_AC": ac,
            "E2E_PM_CASE": str(self.dir),
            "E2E_PM_SLUGS": ",".join(canned.SLUGS),
        }
        if display:
            env["DISPLAY"] = display
        return env

    def guard(self, *args: str, ac: str = "") -> tuple[int, str]:
        """Run one guard role to completion: exit code and output."""
        done = subprocess.run(
            ["/usr/bin/python3", str(ROOT / "scripts/e2e_pm_guard.py"), *args],
            cwd=GUARD,
            env=self.guard_env(ac),
            capture_output=True,
            text=True,
            check=False,
            timeout=40,
        )
        return done.returncode, done.stdout + done.stderr

    def json(self, relative: str) -> dict[str, Any] | None:
        """A JSON file of the case, or ``None``."""
        path = self.dir / relative
        return json.loads(path.read_text("utf-8")) if path.is_file() else None

    def ledger_ids(self, prefix: str) -> list[str]:
        """Guard ledger entry ids starting with ``prefix``."""
        doc = json.loads((self.guard_data / "ledger.json").read_text("utf-8"))
        rows = doc.get("entries", doc)
        ids = (
            rows.keys() if isinstance(rows, dict) else [r.get("entry_id") for r in rows]
        )
        return sorted(str(i) for i in ids if str(i).startswith(prefix))
