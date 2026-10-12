#!/bin/bash

# ============================================================================
# Put a verified tutor change live at once, without disturbing the session.
#
# The live server runs from a frozen release copy, never from the working
# tree, so half-finished edits in ~/src/tutor are never served. A deploy:
#   1. copies a new release,
#   2. smoke-tests it on a scratch port against a copy of today's sessions
#      (it must start, resume the live session and serve valid page JS),
#   3. waits until no reply is in flight (the newest session log does not
#      end on a learner message),
#   4. points `current` at it and restarts tutor.service (install.sh), whose
#      graceful stop drains the old server; the release resumes the session
#      from its transcript (tutor/resume.py).
# The page retries while the server is down, so the learner's next message
# simply lands on the new code.
# ============================================================================

set -euo pipefail

SCRIPT_NAME="$(basename "$0")"
readonly SCRIPT_NAME
REPO="$(cd "$(dirname "$0")/.." && pwd)"
readonly REPO
readonly LIVE_ROOT="$HOME/.local/lib/tutor-live"  # current/ = tutor.service cwd
readonly DATA="${TUTOR_DATA:-$HOME/.local/share/tutor}"
# The live server; it owns the port, the relay and deck-source env, the log.
readonly UNIT="${TUTOR_UNIT:-tutor.service}"
readonly PORT=8778
readonly WEB_BUILD="fvm flutter build web --release --base-href /app/"
SRC="$REPO"
WAIT_LIMIT=300
KEEP_RELEASES=5
TEMP_DIR=""
SMOKE_PID=""

cleanup() {
    if [[ -n "$SMOKE_PID" ]]; then
        kill "$SMOKE_PID" 2>/dev/null || true
    fi
    if [[ -n "$TEMP_DIR" && -d "$TEMP_DIR" ]]; then
        rm -rf "$TEMP_DIR"
    fi
}

trap cleanup EXIT

usage() {
    echo "Usage: $SCRIPT_NAME [--src DIR] [--wait SECONDS]"
    echo "  --src DIR   copy the release from DIR instead of this repo"
    echo "  --wait S    longest wait for an in-flight reply to finish (default 300)"
    exit 0
}

port_pid() {
    ss -ltnpH "sport = :$1" | grep -o 'pid=[0-9]*' | head -n1 | cut -d= -f2
}

session_of() {
    curl -s -m 5 "http://127.0.0.1:$1/api/state" | jq -r '.session_id // empty' || true
}

# Start a scratch server from $1 on port $2 in its own systemd unit; log to $3.
launch() {
    "$REPO/scripts/tutor_launch.sh" "$1" "$2" "$3"
}

# A server on the port outside the unit (a pre-unit launch) blocks its start.
stop_stray() {
    local pid main
    pid="$(port_pid "$PORT" || true)"
    main="$(systemctl --user show -p MainPID --value "$UNIT")"
    if [[ -n "$pid" && "$pid" != "$main" ]]; then
        echo "Stopping pid $pid (on :$PORT outside $UNIT)"
        kill -TERM "$pid"
        # uvicorn finishes in-flight requests before it exits.
        while kill -0 "$pid" 2>/dev/null; do sleep 0.1; done
    fi
}

# A port nothing listens on, so the smoke test can only ever talk to the release.
free_port() {
    local port
    for port in $(seq $((PORT + 10000)) $((PORT + 10100))); do
        if [[ -z "$(port_pid "$port" || true)" ]]; then
            printf '%s\n' "$port"
            return 0
        fi
    done
    echo "No free scratch port" >&2
    exit 1
}

wait_listening() {
    for _ in $(seq 100); do
        if [[ -n "$(port_pid "$1" || true)" ]]; then
            return 0
        fi
        sleep 0.1
    done
    return 1
}

copy_release() {
    mkdir -p "$1"
    rsync -a --exclude .venv --exclude .git --exclude __pycache__ \
        --exclude node_modules --exclude build "$SRC/" "$1/"
    # The Flutter web build (/app/) is built as its own step, not here: it is
    # slow, and a release must never ship a build older than the app source.
    local web="$SRC/app/build/web"
    if [[ ! -f "$web/main.dart.js" ]]; then
        echo "No web build; first run: (cd app && $WEB_BUILD)" >&2
        exit 1
    fi
    if [[ -n "$(find "$SRC/app/lib" "$SRC/app/web" "$SRC/app/pubspec.lock" \
        -newer "$web/main.dart.js" -print -quit)" ]]; then
        echo "The web build is older than app/; rebuild: (cd app && $WEB_BUILD)" >&2
        exit 1
    fi
    mkdir -p "$1/app/build"
    rsync -a "$web/" "$1/app/build/web/"
}

# The release must start, resume the same session and serve parseable JS.
smoke_test() {
    local release="$1" expected="$2" port got dir
    port="$(free_port)"
    TEMP_DIR="$(mktemp -d)"
    mkdir -p "$TEMP_DIR/data"
    # Sessions, and the subjects a curriculum session's cards resolve from.
    for dir in sessions subjects; do
        if [[ -d "$DATA/$dir" ]]; then cp -r "$DATA/$dir" "$TEMP_DIR/data/"; fi
    done
    head -c 32 /dev/urandom >"$TEMP_DIR/key"
    # No deck source: the smoke server's card editor stays read-only.
    # No relay: a temp-data server must never claim real phone requests.
    TUTOR_DATA="$TEMP_DIR/data" TUTOR_KEY="$TEMP_DIR/key" TUTOR_RELAY=0 \
        TUTOR_DECK_SRC="" launch "$release" "$port" "$TEMP_DIR/smoke.log"
    if ! wait_listening "$port"; then
        echo "Smoke test: release did not start:" >&2
        tail -n 20 "$TEMP_DIR/smoke.log" >&2
        exit 1
    fi
    SMOKE_PID="$(port_pid "$port")"
    got="$(session_of "$port")"
    if [[ -n "$expected" && "$got" != "$expected" ]]; then
        echo "Smoke test: expected session '$expected', release resumed '$got'" >&2
        exit 1
    fi
    # Every script the served page loads, read from its own <script> tags so a
    # new file is checked without editing this list; a missing or unparsable
    # one leaves the page blank.
    local script scripts
    curl -sf -m 5 "http://127.0.0.1:$port/" >"$TEMP_DIR/index.html"
    mapfile -t scripts < <(grep -o 'src="/static/[A-Za-z0-9_.-]*\.js"' \
        "$TEMP_DIR/index.html" | sed 's|^src="/static/||; s|"$||')
    if ((${#scripts[@]} == 0)); then
        echo "Smoke test: the page loads no /static/*.js" >&2
        exit 1
    fi
    for script in "${scripts[@]}"; do
        curl -sf -m 5 "http://127.0.0.1:$port/static/$script" >"$TEMP_DIR/$script"
        node --check "$TEMP_DIR/$script"
    done
    echo "Smoke test: node --check ok for ${scripts[*]}"
    curl -sf -m 5 "http://127.0.0.1:$port/api/cards" | jq -e 'length > 0' >/dev/null
    curl -sf -m 5 -o /dev/null "http://127.0.0.1:$port/app/" ||
        { echo "Smoke test: /app/ does not serve the web build" >&2; exit 1; }
    kill "$SMOKE_PID"
    SMOKE_PID=""
    echo "Smoke test passed (session '${got:-none}')."
}

newest_log() {
    local files=("$DATA/sessions/$(date +%Y%m%d)"-*.jsonl)
    if [[ -e "${files[-1]}" ]]; then
        printf '%s\n' "${files[-1]}"
    fi
}

# A reply is in flight while the newest log ends on the learner's message.
wait_idle() {
    local log ticks=0
    log="$(newest_log)"
    [[ -z "$log" ]] && return 0
    while [[ "$(tail -n1 "$log" | jq -r '.type // empty' 2>/dev/null)" == "learner" ]]; do
        if ((ticks == 0)); then
            echo "A reply is in flight; waiting for it to finish..."
        fi
        if ((ticks >= WAIT_LIMIT * 5)); then
            echo "Reply still in flight after ${WAIT_LIMIT}s; not restarting." >&2
            exit 1
        fi
        sleep 0.2
        ticks=$((ticks + 1))
    done
}

prune_releases() {
    local releases=() i excess
    mapfile -t releases < <(find "$LIVE_ROOT/releases" -mindepth 1 -maxdepth 1 -type d | sort)
    excess=$((${#releases[@]} - KEEP_RELEASES))
    for ((i = 0; i < excess; i++)); do
        rm -rf "${releases[i]}"
    done
}

main() {
    local release before after
    systemctl --user cat "$UNIT" >/dev/null 2>&1 ||
        { echo "$UNIT is not installed; run $REPO/install.sh" >&2; exit 1; }
    command -v jq >/dev/null || { echo "jq is required" >&2; exit 1; }
    command -v node >/dev/null || { echo "node is required" >&2; exit 1; }
    # Releases run on the repo venv; the relay needs crdt-sync and httpx in it.
    "$REPO/.venv/bin/python" -c 'import crdt_sync, httpx' 2>/dev/null ||
        { echo "The venv lacks the relay deps; run scripts/setup_dev.sh" >&2; exit 1; }
    release="$LIVE_ROOT/releases/$(date +%Y%m%d-%H%M%S)"
    copy_release "$release"
    echo "Release copied: $release"

    before="$(session_of "$PORT")"
    smoke_test "$release" "$before"

    wait_idle
    stop_stray
    ln -sfn "$release" "$LIVE_ROOT/current"
    systemctl --user restart "$UNIT"
    wait_listening "$PORT" ||
        { echo "Live server did not start; journalctl --user -u $UNIT" >&2; exit 1; }
    after="$(session_of "$PORT")"
    echo "Live on :$PORT from $release (pid $(port_pid "$PORT"))"
    if [[ -n "$before" && "$before" != "$after" ]]; then
        echo "WARNING: session was '$before', now '$after'" >&2
        exit 1
    fi
    echo "Session '${after:-none}' carried over."
    prune_releases
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --src) SRC="$(cd "$2" && pwd)"; shift 2 ;;
        --wait) WAIT_LIMIT="$2"; shift 2 ;;
        -h | --help) usage ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

main "$@"
