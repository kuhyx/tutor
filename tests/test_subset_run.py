# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""A ``-k`` subset run from the system ``python3`` works, as a board check runs it.

The todoImplementer board runs an item's done check as written
(``python3 -m pytest -q tests -k <name>``) with its own venv stripped from
PATH, so ``python3`` is the system one, which has none of tutor's
dependencies; and pyproject's whole-suite ``--cov-fail-under=100`` would fail
any subset. The root ``conftest.py`` re-runs pytest under the repo's
``.venv`` and lifts the whole-suite coverage gate for ``-k`` runs only.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
SYSTEM_PYTHON = "/usr/bin/python3"
ARGS = ("tests", "-k", "card_code_field_absent")


@pytest.mark.skipif(
    not (ROOT / ".venv/bin/python").is_file() or shutil.which(SYSTEM_PYTHON) is None,
    reason="needs the repo .venv and a system python3 (a dev checkout)",
)
def test_a_keyword_subset_runs_from_the_system_python(tmp_path: Path) -> None:
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"VIRTUAL_ENV", "PYTEST_XDIST_WORKER", "PYTEST_ADDOPTS"}
        and not k.startswith(("COV_CORE_", "PYTEST_"))
    }
    env["PATH"] = "/usr/local/bin:/usr/bin:/bin"
    env["COVERAGE_FILE"] = str(tmp_path / "coverage")  # never the outer run's
    run = subprocess.run(
        [SYSTEM_PYTHON, "-m", "pytest", "-q", "-p", "no:cacheprovider", *ARGS],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=50,
        check=False,
    )
    assert run.returncode == 0, run.stdout[-2000:] + run.stderr[-2000:]
    assert run.stdout.split()[:2] == [".", "[100%]"]  # one test ran and passed
    assert "coverage gate skipped" in run.stdout
