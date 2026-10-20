#!/bin/bash
# ============================================================================
# Agent E2E sandbox: the real web build and the real engine + relay, against
# a COPY of the data dir and a local Firebase RTDB emulator. Never the live
# data dir, ledger, RTDB, device id, :8778 or tutor.service. Each command
# stays under 60 s; the emulator and the server run as transient user units.
#
# Usage:
#   scripts/e2e_sandbox.sh build              # e2e web build (once per app change)
#   scripts/e2e_sandbox.sh up [--new-cap N] [--as-of "YYYY-MM-DD HH:MM[:SS]"]
#                                    # fresh sandbox; N forces the daily limit,
#                                    # --as-of rewinds the copy (e2e_prepare.py)
#   scripts/e2e_sandbox.sh flow F1|F2|F3|F4 [send|wait|check]
#                                    # drive one flow; exit 0 = PASS. A tutor
#                                    # turn can outlast 60 s, so F1/F3/F4 run
#                                    # as send, wait (75 = still pending: call
#                                    # it again), check (e2e_drive.py)
#   scripts/e2e_sandbox.sh down               # stop units, delete the sandbox
# Env: E2E_SUBJECT, E2E_CARD (the card a flow must start), E2E_DISPLAY (:97),
# E2E_SESSION (F3/F4: the session at card end; up --as-of "2026-10-20 17:24:30").
# The app reaches the emulator through scripts/e2e_h2proxy.go (HTTP/2 over
# TLS, as the real database): over the emulator's HTTP/1.1 Chrome's 6
# connections per host are all held by the session screen's streams.
# Needs: java + the cached RTDB emulator jar (firebase-tools), go, chromium,
# an Xvfb on E2E_DISPLAY, fvm.
# ============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly ROOT
readonly PY="$ROOT/.venv/bin/python"
# This checkout's tutor package, not whatever the venv's editable install names.
export PYTHONPATH="$ROOT"
readonly STATE="$ROOT/build/e2e-sandbox/state"
readonly SCREENS="$ROOT/app/build/screens"
readonly WEB="$ROOT/app/build/web_e2e"
readonly SRC_DATA="$HOME/.local/share/tutor"
readonly SUBJECT="${E2E_SUBJECT:-chc-rozumie-poj-cia-z-maila-do-centrum}"
readonly CARD="${E2E_CARD:-vhost-what}"
readonly SESSION="${E2E_SESSION:-20261020-172115-3f84}"
readonly DISPLAY_ID="${E2E_DISPLAY:-:97}"
readonly DB_UNIT="tutor-e2e-db"
readonly SERVER_UNIT="tutor-e2e-server"
readonly PROXY_UNIT="tutor-e2e-h2"
readonly PROXY="$ROOT/build/e2e-sandbox/h2proxy"

die() { echo "e2e_sandbox: $*" >&2; exit 1; }

# A free loopback port in 20000-29999 (never 8778).
free_port() {
    local port
    for _ in {1..50}; do
        port=$((20000 + RANDOM % 10000))
        ss -ltnH "sport = :$port" | grep -q . || { echo "$port"; return 0; }
    done
    die "no free port"
}

# Poll a URL until it answers (up to $2 half-seconds).
wait_http() {
    local url="$1" tries="$2"
    for ((i = 0; i < tries; i++)); do
        curl -sf -o /dev/null "$url" && return 0
        sleep 0.5
    done
    return 1
}

emulator_jar() {
    local jar
    jar="$(find "$HOME/.cache/firebase/emulators" -maxdepth 1 \
        -name 'firebase-database-emulator-v*.jar' 2>/dev/null | sort -V | tail -1)"
    [[ -n "$jar" ]] || die "no RTDB emulator jar; run: firebase setup:emulators:database"
    echo "$jar"
}

cmd_build() {
    cd "$ROOT/app"
    [[ -f lib/config/firebase_local.dart ]] ||
        fvm dart run tool/write_firebase_config.dart --placeholder
    CAP_CPU_PCT=20 CAP_MEM=4G "$HOME/.claude/scripts/capped.sh" fvm flutter build web \
        --release -t tool/e2e/main.dart -o build/web_e2e --base-href /app/
}

cmd_down() {
    local unit
    for unit in "$SERVER_UNIT" "$PROXY_UNIT" "$DB_UNIT"; do  # one by one: a
        systemctl --user stop "$unit" 2>/dev/null || true    # missing unit fails all
    done
    if [[ -f "$STATE" ]]; then
        local sandbox
        sandbox="$(sed -n 's/^SANDBOX=//p' "$STATE")"
        [[ "$sandbox" == */tutor-e2e.* && -d "$sandbox" ]] && {
            cp "$sandbox/server.log" "$(dirname "$STATE")/last-server.log" 2>/dev/null || true
            rm -rf "$sandbox"
        }
        rm -f "$STATE"
    fi
    rm -f "$(dirname "$STATE")"/f[1-4].json  # a phased flow's send state
    echo "e2e sandbox down"
}

cmd_up() {
    [[ -f "$WEB/index.html" ]] || die "no e2e web build: run $0 build"
    cmd_down >/dev/null
    local sandbox db_port port dev db h2_port
    sandbox="$(mktemp -d "${TMPDIR:-/tmp}/tutor-e2e.XXXXXX")"
    dev="$("$PY" "$ROOT/scripts/e2e_prepare.py" "$SRC_DATA" "$sandbox/data" "$@")"
    head -c 32 /dev/urandom | base64 > "$sandbox/test.key"
    mkdir -p "$(dirname "$STATE")" "$sandbox/cache"
    db_port="$(free_port)"
    port="$(free_port)"
    h2_port="$(free_port)"
    db="http://127.0.0.1:$db_port"
    printf 'SANDBOX=%s\nDB=%s\nAPP_DB=%s\nPORT=%s\nDEV=%s\n' \
        "$sandbox" "$db" "https://127.0.0.1:$h2_port" "$port" "$dev" > "$STATE"
    [[ "$PROXY" -nt "$ROOT/scripts/e2e_h2proxy.go" ]] ||
        "$HOME/.claude/scripts/capped.sh" go build -o "$PROXY" "$ROOT/scripts/e2e_h2proxy.go"
    systemd-run --user --quiet --collect --unit="$DB_UNIT" -p RuntimeMaxSec=3600 \
        java -jar "$(emulator_jar)" --host 127.0.0.1 --port "$db_port"
    wait_http "$db/.json" 40 || die "emulator did not start"
    systemd-run --user --quiet --collect --unit="$PROXY_UNIT" -p RuntimeMaxSec=3600 \
        "$PROXY" -listen "127.0.0.1:$h2_port" -target "$db"
    for _ in {1..20}; do
        curl -sfk -o /dev/null "https://127.0.0.1:$h2_port/.json" && break
        sleep 0.25
    done
    systemd-run --user --quiet --collect --unit="$SERVER_UNIT" -p RuntimeMaxSec=3600 \
        -p WorkingDirectory="$ROOT" \
        -p StandardOutput="file:$sandbox/server.log" -p StandardError="file:$sandbox/server.log" \
        -E TUTOR_DATA="$sandbox/data" -E TUTOR_KEY="$sandbox/test.key" \
        -E TUTOR_WEBAPP_DIR="$WEB" -E TUTOR_IMAGE_CACHE="$sandbox/cache/images" \
        -E TUTOR_SOURCE_CACHE="$sandbox/cache/sources" -E TUTOR_WIKI_CACHE="$sandbox/cache/wiki" \
        -E TUTOR_ANKI_COLLECTION="$sandbox/cache/none.anki2" -E PATH="$PATH" -E PYTHONPATH="$ROOT" \
        "$PY" "$ROOT/scripts/e2e_server.py" --db "$db" --port "$port" --subject "$SUBJECT"
    wait_http "http://127.0.0.1:$port/api/state" 80 || {
        tail -20 "$sandbox/server.log" >&2
        die "server did not start"
    }
    # The worker is serving once its presence beat is in the emulator.
    for _ in {1..30}; do
        [[ "$(curl -sf "$db/tutor/v1/presence/workers/$dev.json")" != "null" ]] && break
        sleep 0.5
    done
    grep 'e2e seed' "$sandbox/server.log" || true
    echo "e2e sandbox up: app http://127.0.0.1:$port/app/?db=https://127.0.0.1:$h2_port worker $dev"
}

cmd_flow() {
    local flow="${1:?flow F1|F2|F3|F4}" phase="${2:-all}" db app_db port sandbox
    [[ -f "$STATE" ]] || die "no sandbox: run $0 up"
    db="$(sed -n 's/^DB=//p' "$STATE")"
    app_db="$(sed -n 's/^APP_DB=//p' "$STATE")"
    port="$(sed -n 's/^PORT=//p' "$STATE")"
    sandbox="$(sed -n 's/^SANDBOX=//p' "$STATE")"
    "$PY" "$ROOT/scripts/e2e_drive.py" "$flow" "$phase" --app "http://127.0.0.1:$port/app/" \
        --db "$db" --app-db "$app_db" --card "$CARD" --display "$DISPLAY_ID" \
        --data "$sandbox/data" --session "$SESSION" \
        --state "$(dirname "$STATE")/${flow,,}.json" --out "$SCREENS/e2e_${flow,,}"
}

main() {
    local cmd="${1:-}"
    shift || true
    case "$cmd" in
        build) cmd_build ;;
        up) cmd_up "$@" ;;
        flow) cmd_flow "$@" ;;
        down) cmd_down ;;
        *) die "usage: $0 build | up [--new-cap N] [--as-of T] | flow F1|F2|F3|F4 [send|wait|check] | down" ;;
    esac
}

main "$@"
