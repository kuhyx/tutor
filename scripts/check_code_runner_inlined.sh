#!/bin/bash

# ============================================================================
# Check that code_runner now lives inside this repo (packages/code_runner)
# instead of being a git dependency on kuhyx/utils, and that nothing broke:
#   1. the in-repo package exists and is the one the venv imports
#   2. pyproject.toml has no kuhyx/utils dependency for code-runner
#   3. kuhyx/utils (origin/main of ~/src/utils) no longer carries code_runner/
#   4. the whole suite passes (100% branch coverage is in pyproject's addopts)
# ============================================================================

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly REPO_DIR
readonly PKG_DIR="${REPO_DIR}/packages/code_runner"
readonly UTILS_DIR="${UTILS_ROOT:-$HOME/src/utils}"
readonly PY="${REPO_DIR}/.venv/bin/python"
failed=0

fail() { printf 'FAIL: %s\n' "$*" >&2; failed=1; }
ok() { printf 'ok:   %s\n' "$*"; }

check_in_repo() {
    if [[ -f "${PKG_DIR}/pyproject.toml" && -f "${PKG_DIR}/code_runner/__init__.py" ]]; then
        ok "package lives at packages/code_runner"
    else
        fail "packages/code_runner is missing"
    fi
    local where
    where="$(cd / && "$PY" -c 'import code_runner; print(code_runner.__file__)' 2>&1 || true)"
    if [[ "$where" == "${PKG_DIR}/"* ]]; then
        ok "venv imports the in-repo copy"
    else
        fail "venv imports code_runner from: ${where}"
    fi
}

check_no_utils_dep() {
    if grep -Eq 'code[-_]runner.*kuhyx/utils|kuhyx/utils.*code_runner' "${REPO_DIR}/pyproject.toml"; then
        fail "pyproject.toml still depends on code_runner via kuhyx/utils"
    else
        ok "pyproject.toml has no kuhyx/utils dependency for code_runner"
    fi
}

# Judged on utils' origin/main, not its working tree: a checkout can lag behind
# (or carry another session's uncommitted edits) without the module being there.
check_removed_from_utils() {
    git -C "$UTILS_DIR" fetch -q origin main
    if [[ -n "$(git -C "$UTILS_DIR" ls-tree --name-only origin/main -- code_runner)" ]]; then
        fail "origin/main of utils still has code_runner/"
    else
        ok "utils origin/main has no code_runner directory"
    fi
    if [[ -e "${UTILS_DIR}/code_runner" ]]; then
        printf 'warn: %s/code_runner still in the local checkout (pull it)\n' "$UTILS_DIR"
    fi
}

check_tests() {
    if (cd "$REPO_DIR" && "$PY" -m pytest -p no:cacheprovider -q 2>&1 | tail -4); then
        ok "test suite ran"
    else
        fail "test suite failed"
    fi
}

main() {
    check_in_repo
    check_no_utils_dep
    check_removed_from_utils
    check_tests
    exit "$failed"
}

main "$@"
