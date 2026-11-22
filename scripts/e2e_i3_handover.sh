#!/bin/bash
# ============================================================================
# Agent E2E F26: `tutor --route /learn/S/M` must SHOW the tutor under i3 (C4).
#
# The LeetCode lock's learn button launches it while kuhy looks at the lock.
# F25 proves the launch is handed to the tutor window already open; this one
# proves kuhy then sees that window when i3 held it on a workspace that was
# not shown. It runs the real launcher (run.sh, what ~/.local/bin/tutor
# execs) against the e2e sandbox on a private Xvfb with its own i3: kuhy's i3
# config without the bar and the exec lines that start his apps. Never his
# display, never his i3 socket. Xvfb, i3 and the driver (with its Chrome) are
# transient user units, stopped on exit.
#
# Usage (each call < 60 s):
#   scripts/e2e_sandbox.sh up --phase "theory leetcode-easy-algorithms-in-typescript/prefix-sums"
#   scripts/e2e_i3_handover.sh [shot.png]     # exit 0 = PASS
#   scripts/e2e_sandbox.sh down
# shot.png is the Xvfb root after the launch, pass or fail (default
# app/build/screens/e2e_i3_handover.png): Read it.
# Needs: Xvfb, i3, chromium, import (imagemagick), a sandbox that is up.
# ============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly ROOT
readonly PY="$ROOT/.venv/bin/python"
readonly STATE="$ROOT/build/e2e-sandbox/state"
readonly I3_CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}/i3/config"
# Per checkout, as the sandbox's units are: worktrees never stop each other's.
TAG="$(printf '%s' "$ROOT" | md5sum | cut -c1-8)"
readonly TAG
readonly XVFB_UNIT="tutor-i3-xvfb-$TAG"
readonly WM_UNIT="tutor-i3-wm-$TAG"
readonly DRIVE_UNIT="tutor-i3-drive-$TAG"
WORK=""

die() { echo "e2e_i3_handover: $*" >&2; exit 1; }

cleanup() {
    local unit
    for unit in "$DRIVE_UNIT" "$WM_UNIT" "$XVFB_UNIT"; do
        systemctl --user stop "$unit" 2>/dev/null || true
    done
    [[ -z "$WORK" ]] || rm -rf "$WORK"
}

# A display number no X server holds (never kuhy's :0).
free_display() {
    local n
    for n in {140..199}; do
        [[ -e "/tmp/.X11-unix/X$n" || -e "/tmp/.X$n-lock" ]] || { echo "$n"; return 0; }
    done
    die "no free display in :140..:199"
}

# kuhy's i3 config without what reaches outside the nested i3: the bar block,
# the exec lines (his apps and units) and any fixed socket path.
nested_config() {
    awk '
        /^[[:space:]]*bar[[:space:]]*\{/ { depth = 1; next }
        depth { depth += gsub(/\{/, "{") - gsub(/\}/, "}"); next }
        /^[[:space:]]*(exec|exec_always|ipc-socket|ipc_socket)[[:space:]]/ { next }
        { print }
    ' "$I3_CONFIG"
}

# Poll a test command (up to $1 quarter-seconds).
wait_for() {
    local tries="$1" i
    shift
    for ((i = 0; i < tries; i++)); do
        "$@" >/dev/null 2>&1 && return 0
        sleep 0.25
    done
    return 1
}

main() {
    local shot="${1:-$ROOT/app/build/screens/e2e_i3_handover.png}" n sock port db code=0
    [[ -f "$STATE" ]] || die "no sandbox: run scripts/e2e_sandbox.sh up --phase \"theory S/M\""
    [[ -f "$I3_CONFIG" ]] || die "no i3 config at $I3_CONFIG"
    port="$(sed -n 's/^PORT=//p' "$STATE")"
    db="$(sed -n 's/^DB=//p' "$STATE")"
    trap cleanup EXIT
    cleanup  # a run that was killed mid-way
    WORK="$(mktemp -d "${TMPDIR:-/tmp}/tutor-i3.XXXXXX")"
    n="$(free_display)"
    sock="$WORK/i3.sock"
    nested_config > "$WORK/i3.config"
    systemd-run --user --quiet --collect --unit="$XVFB_UNIT" -p RuntimeMaxSec=120 \
        Xvfb ":$n" -screen 0 1920x1080x24 -nolisten tcp
    wait_for 40 test -S "/tmp/.X11-unix/X$n" || die "Xvfb :$n did not start"
    # I3SOCK is where i3 creates its socket; without it i3-msg would find none.
    systemd-run --user --quiet --collect --unit="$WM_UNIT" -p RuntimeMaxSec=120 \
        -E DISPLAY=":$n" -E I3SOCK="$sock" i3 -c "$WORK/i3.config"
    wait_for 40 i3-msg -s "$sock" -t get_version || die "the nested i3 did not start"
    # The driver is a unit too: its Chrome dies with it, whatever kills this call.
    systemd-run --user --quiet --collect --wait --pipe --unit="$DRIVE_UNIT" \
        -p RuntimeMaxSec=55 -p WorkingDirectory="$ROOT" \
        -E DISPLAY=":$n" -E I3SOCK="$sock" -E PATH="$PATH" -E PYTHONPATH="$ROOT" \
        "$PY" "$ROOT/scripts/e2e_i3_handover.py" --app "http://127.0.0.1:$port/app/" \
        --db "$db" --display ":$n" --sock "$sock" --shot "$shot" || code=$?
    exit "$code"
}

main "$@"
