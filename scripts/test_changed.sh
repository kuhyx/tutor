#!/bin/bash

# ============================================================================
# Run only the tests related to files changed vs HEAD (staged, unstaged and
# untracked), Python and the Flutter app. Quiet: failures plus a summary.
# Falls back to a full suite when a change cannot be mapped to a test file.
# ============================================================================

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
readonly PY=".venv/bin/python"
full=0 touched=0 app_full=0 app_touched=0
tests=() app_tests=()

# tutor/<mod>.py -> tutor/tests/test_<mod>.py, else tests/test_<mod>.py
# (cards and sources keep their tests at the top level).
test_for() {
    local base="$1" t
    for t in "tutor/tests/test_${base#_}.py" "tests/test_${base#_}.py"; do
        if [[ -f "$t" ]]; then printf '%s\n' "$t"; return 0; fi
    done
    return 1
}

while IFS= read -r f; do
    [[ -n "$f" && -e "$f" ]] || continue
    case "$f" in
        pyproject.toml | */conftest.py | conftest.py | tests/_*.py | tutor/tests/_*.py) full=1; touched=1 ;;
        tests/test_*.py | tutor/tests/test_*.py) touched=1; tests+=("$f") ;;
        subjects/*/deck/*.json) full=1; touched=1 ;;
        tutor/*.py)
            touched=1
            if t="$(test_for "$(basename "$f" .py)")"; then tests+=("$t"); else full=1; fi
            ;;
        # Flutter client: lib/<x>.dart -> test/<x>_test.dart; a UI file or
        # anything unmapped runs the whole app suite.
        app/test/*_test.dart) app_touched=1; app_tests+=("${f#app/}") ;;
        app/lib/*.dart | app/test/*.dart | app/tool/*.dart | app/pubspec.*)
            app_touched=1
            t="app/test/${f#app/lib/}"
            t="${t%.dart}_test.dart"
            if [[ "$f" == app/lib/* && -f "$t" ]]; then app_tests+=("${t#app/}"); else app_full=1; fi
            ;;
    esac
done < <({ git diff --name-only HEAD 2>/dev/null || git ls-files; git ls-files --others --exclude-standard; } | sort -u)

# The app's tests, capped like every heavy run here (2 GiB is too tight
# for the Flutter test compiler: 4 GiB, 20 % CPU).
run_app() {
    local -a cmd=(fvm flutter test "$@")
    if [[ -x "$HOME/.claude/scripts/capped.sh" ]]; then
        (cd app && CAP_MEM=4G CAP_CPU_PCT=20 "$HOME/.claude/scripts/capped.sh" "${cmd[@]}")
    else
        (cd app && "${cmd[@]}")
    fi
}

if [[ $touched -eq 0 && $app_touched -eq 0 ]]; then
    echo "no python or app changes vs HEAD: nothing to test"; exit 0
fi
rc=0
if [[ $full -eq 1 ]]; then
    echo "python: running full suite"
    "$PY" -m pytest -q --tb=short || rc=1
elif [[ $touched -eq 1 ]]; then
    mapfile -t uniq < <(printf '%s\n' "${tests[@]}" | sort -u)
    echo "python: ${#uniq[@]} test file(s)"
    "$PY" -m pytest -q --tb=short --no-cov "${uniq[@]}" || rc=1
fi
if [[ $app_full -eq 1 ]]; then
    echo "app: running full suite"
    run_app || rc=1
elif [[ $app_touched -eq 1 ]]; then
    mapfile -t app_uniq < <(printf '%s\n' "${app_tests[@]}" | sort -u)
    echo "app: ${#app_uniq[@]} test file(s)"
    run_app "${app_uniq[@]}" || rc=1
fi
[[ $rc -eq 0 ]] && echo "test-changed: pass" || echo "test-changed: FAIL"
exit $rc
