#!/bin/bash
# ============================================================================
# A sandbox worker for a phone slot build (com.kuhy.slotN, built with
# `phone_deploy.sh --slot`, so SYNC_NAMESPACE=sandbox/slotN). It runs the real
# engine + relay on a COPY of the data dir against the REAL database, but
# every path sits under /sandbox/slotN/ (TUTOR_SYNC_NAMESPACE), so the slot
# app sees subjects, due counts and paid minutes while the live tree, ledger,
# device id, :8778 and tutor.service stay untouched.
#
# Usage:
#   scripts/e2e_slot.sh up <n>     # copy the data, start the worker for slot n
#   scripts/e2e_slot.sh status     # unit state, port, the copy's path
#   scripts/e2e_slot.sh down       # stop the worker, delete the copy
#
# The copy gets its own HOME: the session file and the crdt-sync files are
# copied in, so token refreshes never write the live worker's session file.
# Every Claude call goes to a closed port (ANTHROPIC_BASE_URL, as
# e2e_sandbox.sh --model-down network) and the LeetCode guard route too.
# Sign in on the slot with the sync account; unlock with the crdt-sync
# password (~/.config/crdt-sync/password).
# ============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly ROOT
readonly PY="$ROOT/.venv/bin/python"
readonly SRC_DATA="$HOME/.local/share/tutor"
readonly DIR="${E2E_SLOT_DIR:-$ROOT/build/e2e-slot}"
TAG="$(printf '%s' "$ROOT" | md5sum | cut -c1-8)"
readonly UNIT="tutor-e2e-slot-$TAG"

die() { printf 'e2e_slot: %s\n' "$1" >&2; exit 1; }

free_port() {
    "$PY" -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1])'
}

# The secrets the worker needs, copied into the sandbox HOME (never linked).
seed_home() {
    local home="$1" f
    mkdir -p "$home/.config/tutor" "$home/.config/crdt-sync"
    cp "$HOME/.config/tutor/firebase_auth.json" "$home/.config/tutor/"
    for f in firebase.json password; do
        cp "$HOME/.config/crdt-sync/$f" "$home/.config/crdt-sync/"
    done
    chmod -R go-rwx "$home"
}

up() {
    local n="${1:?up needs the slot number}" port dev
    [[ "$n" =~ ^[0-9]+$ ]] || die "slot number must be digits, got '$n'"
    systemctl --user is-active --quiet "$UNIT" && die "already up: $0 down first"
    rm -rf "$DIR"
    mkdir -p "$DIR/cache"
    seed_home "$DIR/home"
    head -c 32 /dev/urandom | base64 > "$DIR/test.key"
    dev="$("$PY" "$ROOT/scripts/e2e_prepare.py" "$SRC_DATA" "$DIR/data")"
    port="$(free_port)"
    printf 'SLOT=%s\nPORT=%s\nDEV=%s\n' "$n" "$port" "$dev" > "$DIR/state"
    systemd-run --user --quiet --collect --unit="$UNIT" -p RuntimeMaxSec=7200 \
        -p WorkingDirectory="$ROOT" \
        -p StandardOutput="append:$DIR/server.log" -p StandardError="append:$DIR/server.log" \
        -E HOME="$DIR/home" -E TUTOR_SYNC_NAMESPACE="sandbox/slot$n" -E TUTOR_RELAY=1 \
        -E TUTOR_DATA="$DIR/data" -E TUTOR_KEY="$DIR/test.key" \
        -E TUTOR_IMAGE_CACHE="$DIR/cache/images" -E TUTOR_SOURCE_CACHE="$DIR/cache/sources" \
        -E TUTOR_WIKI_CACHE="$DIR/cache/wiki" -E TUTOR_ANKI_COLLECTION="$DIR/cache/none.anki2" \
        -E FOCUS_PROJECT_DATA="$DIR/focus" -E XDG_STATE_HOME="$DIR/state.d" \
        -E XDG_DATA_HOME="$DIR/home/.local/share" -E TUTOR_GUARD_DATA="$DIR/guard" \
        -E TUTOR_THEORY_PHASE="$DIR/theory_phase.json" \
        -E TUTOR_LOCAL_MODEL_URL=http://127.0.0.1:9 -E TUTOR_FREE_GATEWAY=http://127.0.0.1:9 \
        -E ANTHROPIC_BASE_URL=http://127.0.0.1:9 -E CLAUDE_CODE_MAX_RETRIES=0 \
        -E TUTOR_GUARD_THEORY_URL=http://127.0.0.1:9/api/theory \
        -E PATH="$PATH" -E PYTHONPATH="$ROOT" \
        "$PY" -m tutor --port "$port" --fresh
    for _ in $(seq 40); do
        grep -q 'Firebase relay enabled' "$DIR/server.log" 2>/dev/null && break
        systemctl --user is-active --quiet "$UNIT" || { tail -20 "$DIR/server.log" >&2; die "worker exited"; }
        sleep 1
    done
    grep -q 'Firebase relay enabled' "$DIR/server.log" || die "no relay after 40 s (see $DIR/server.log)"
    echo "e2e slot worker up: sandbox/slot$n, device $dev, http://127.0.0.1:$port/"
}

status() {
    systemctl --user is-active "$UNIT" || true
    [[ -f "$DIR/state" ]] && cat "$DIR/state"
    echo "DIR=$DIR"
}

down() {
    systemctl --user stop "$UNIT" 2>/dev/null || true
    rm -rf "$DIR"
    echo "e2e slot worker down"
}

main() {
    case "${1:-}" in
        up) up "${2:-}" ;;
        status) status ;;
        down) down ;;
        *) sed -n '/^# Usage:/,/^#$/p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
    esac
}

main "$@"; exit $?
