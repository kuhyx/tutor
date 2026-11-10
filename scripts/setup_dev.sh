#!/bin/bash
# ============================================================================
# setup_dev.sh -- the dev venv the pre-commit gate and the test suite run in.
#
# .venv holds tutor and the in-repo code_runner (both editable)
# plus the pinned test and lint tools. Idempotent.
# ============================================================================

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly REPO_DIR
readonly VENV="${REPO_DIR}/.venv"

if [[ ! -x "${VENV}/bin/python" ]]; then
    python3 -m venv "$VENV"
fi
"${VENV}/bin/python" -m pip install --quiet --upgrade pip
# code_runner first: tutor imports it but does not declare it (see pyproject).
"${VENV}/bin/python" -m pip install --quiet --no-deps -e "${REPO_DIR}/packages/code_runner"
"${VENV}/bin/python" -m pip install --quiet -e "${REPO_DIR}[dev]"
"${VENV}/bin/python" -c "import code_runner, tutor, pytest, mypy, pylint; print('dev venv OK')"
