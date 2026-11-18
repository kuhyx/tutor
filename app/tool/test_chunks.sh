#!/bin/bash
# ============================================================================
# test_chunks.sh -- the full app suite + coverage gate, in calls under 60 s.
#
# `flutter test --total-shards` splits TESTS, not files: every shard still
# compiles all ~180 test files (~37 s), so no shard ever got faster. This
# splits the FILES into CHUNKS groups instead. Each call runs the next chunk
# not yet green, then more while the call is under BUDGET_S; when every
# chunk is green it merges their lcov and runs tool/check_coverage.dart.
# Repeat until it prints "All tests passed" (exit 0); exit 75 = call again.
#
# Progress lives in build/test_chunks/<key>/, keyed by a hash of lib/, test/,
# tool/ and pubspec.lock: any edit starts over, an unchanged tree resumes.
#
# Usage (from anywhere): app/tool/test_chunks.sh [--fresh]
# Needs: fvm, lcov, sha256sum; ~/.claude/scripts/capped.sh when present.
# ============================================================================

set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly APP_DIR
readonly CHUNKS="${TEST_CHUNKS:-6}"  # ~30 files, ~20 s each with coverage
readonly BUDGET_S="${TEST_CHUNK_BUDGET_S:-20}"  # start another chunk only below this
readonly CAPPED="$HOME/.claude/scripts/capped.sh"
readonly PENDING=75

die() { echo "test_chunks: $*" >&2; exit 1; }

tree_key() {
    # Content hash of everything a test result depends on.
    (cd "$APP_DIR" && find lib test tool pubspec.lock -type f \( -name '*.dart' -o -name '*.json' -o -name pubspec.lock \) -print0 \
        | sort -z | xargs -0 sha256sum | sha256sum | cut -c1-16)
}

chunk_files() {
    # Every CHUNKS-th test file, starting at index $1 (stable sorted order).
    (cd "$APP_DIR" && find test -name '*_test.dart' | sort | awk -v k="$CHUNKS" -v i="$1" 'NR % k == i')
}

run_chunk() {
    local i="$1" state="$2" log
    log="$state/chunk_$i.log"
    local -a files runner=()
    mapfile -t files < <(chunk_files "$i")
    [[ -x "$CAPPED" ]] && runner=(env CAP_CPU_PCT=20 CAP_MEM=4G "$CAPPED")
    echo "chunk $((i + 1))/$CHUNKS: ${#files[@]} files"
    local rc=0
    (cd "$APP_DIR" && "${runner[@]}" fvm flutter test --no-pub --no-dds --concurrency=4 \
        --coverage --coverage-path "$state/chunk_$i.info" "${files[@]}") >"$log" 2>&1 || rc=$?
    # A SIGTERMed run can exit 0: trust only the reporter's last verdict.
    if [[ $rc -ne 0 ]] || ! grep -q 'All tests passed!' "$log"; then
        grep -E '^\s*(Expected|Actual|Which)|\[E\]|Some tests failed|^Failing|test/.*_test\.dart' "$log" | tail -30
        die "chunk $((i + 1)) failed (rc=$rc); full log: $log"
    fi
    touch "$state/chunk_$i.ok"
}

finish() {
    local state="$1" i
    local -a merge=()
    for ((i = 0; i < CHUNKS; i++)); do merge+=(-a "$state/chunk_$i.info"); done
    lcov --quiet "${merge[@]}" -o "$APP_DIR/coverage/lcov.info" --ignore-errors empty,inconsistent >/dev/null
    (cd "$APP_DIR" && fvm dart run tool/check_coverage.dart coverage/lcov.info) || die "coverage gate failed"
    echo "All tests passed ($CHUNKS chunks, key $(basename "$state"))"
}

main() {
    command -v lcov >/dev/null || die "lcov missing: sudo pacman -S lcov"
    local key state start i
    key="$(tree_key)"
    state="$APP_DIR/build/test_chunks/$key-k$CHUNKS"
    [[ "${1:-}" == "--fresh" ]] && rm -rf "$APP_DIR/build/test_chunks"
    mkdir -p "$state" "$APP_DIR/coverage"
    start=$SECONDS
    for ((i = 0; i < CHUNKS; i++)); do
        [[ -f "$state/chunk_$i.ok" ]] && continue
        if ((SECONDS - start >= BUDGET_S)); then
            echo "pending: chunk $((i + 1))/$CHUNKS next; run again"
            exit "$PENDING"
        fi
        run_chunk "$i" "$state"
        echo "chunk $((i + 1))/$CHUNKS passed ($((SECONDS - start)) s)"
    done
    finish "$state"
}

main "$@"
