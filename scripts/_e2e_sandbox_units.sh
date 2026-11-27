# shellcheck shell=bash
# ============================================================================
# Ports, waits and the transient units behind scripts/e2e_sandbox.sh: the
# emulator jar, how Claude fails (F14) and the sandbox server. Sourced only by
# e2e_sandbox.sh, which defines ROOT, PY, STATE, WEB, SUBJECT, FOCUS_SRC, the
# unit names and die() before sourcing this file.
# ============================================================================
# shellcheck disable=SC2154  # every global here is set by e2e_sandbox.sh

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

# The server's -E flags for how Claude fails (F14): `network` points the
# CLI at a closed port (an outage, reason network), `refuse` at a stub that
# answers 400 (a model error); none = the real API.
# Sets MODEL_ENV; fails loudly (never a silent fall back to the real API).
MODEL_ENV=()
model_env() {
    local mode="$1" port
    MODEL_ENV=()
    systemctl --user stop "$MODEL_UNIT" 2>/dev/null || true
    case "$mode" in
        "" | none) return 0 ;;
        network) port=9 ;;
        refuse)
            port="$(free_port)"
            systemd-run --user --quiet --collect --unit="$MODEL_UNIT" -p RuntimeMaxSec=3600 \
                "$PY" "$ROOT/scripts/e2e_model_stub.py" --port "$port"
            # It answers 400 to everything: any HTTP status means it is up.
            for _ in {1..40}; do
                [[ "$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$port/")" != 000 ]] && break
                sleep 0.25
            done
            [[ "$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$port/")" == 400 ]] ||
                die "model stub did not start"
            ;;
        *) die "--model-down network|refuse|none, not $mode" ;;
    esac
    MODEL_ENV=(-E "ANTHROPIC_BASE_URL=http://127.0.0.1:$port" -E CLAUDE_CODE_MAX_RETRIES=0)
}

# The LeetCode bar's guard route (DOCS-contract-leetcode-bar.md): the sandbox
# server never reads the live guard (:8771). $1 = the canned "theory" JSON ($2 =
# the CLOCK): a stub serves it on a sandbox port; none: a closed port, so the
# bar's numbers are unknown. Sets GUARD_ENV.
readonly GUARD_UNIT="tutor-e2e-guard-${TAG:-x}"
GUARD_ENV=(-E TUTOR_GUARD_THEORY_URL=http://127.0.0.1:9/api/theory)
guard_env() {
    local body="$1" clock="$2" port
    systemctl --user stop "$GUARD_UNIT" 2>/dev/null || true
    [[ -n "$body" ]] || return 0
    port="$(free_port)"
    systemd-run --user --quiet --collect --unit="$GUARD_UNIT" -p RuntimeMaxSec=3600 \
        "$PY" "$ROOT/scripts/e2e_guard_stub.py" --port "$port" --body "$body" \
        --day "$(date -d "${clock:-now}" +%F)"
    wait_http "http://127.0.0.1:$port/api/theory" 40 || die "guard stub did not start"
    GUARD_ENV=(-E "TUTOR_GUARD_THEORY_URL=http://127.0.0.1:$port/api/theory")
}

# The guard's C3 row in the sandbox ($1), signed with the sandbox key:
# theory S/M..., solve, bad S/M (a wrong hmac) or missing (no file).
write_phase() {
    local sandbox="$1"
    shift
    "$PY" "$ROOT/scripts/e2e_phase.py" write "$sandbox/theory_phase.json" \
        --key "$sandbox/test.key" "$@"
}

# Start the sandbox server on the state file's sandbox (up, restart). A
# CLOCK runs it under libfaketime from that moment on: the worker's "today".
# XDG_STATE_HOME stays in the sandbox: its staged model faults (F14, a
# --model-down restart) must never reach kuhy's app-errors board. The C3
# phase file is the sandbox's too (`phase`), never the guard's live one; so
# is the guard dir the rework chat reads (TUTOR_GUARD_DATA, F29).
start_server() {
    local sandbox db port dev clock
    sandbox="$(sed -n 's/^SANDBOX=//p' "$STATE")"
    db="$(sed -n 's/^DB=//p' "$STATE")"
    port="$(sed -n 's/^PORT=//p' "$STATE")"
    dev="$(sed -n 's/^DEV=//p' "$STATE")"
    clock="$(sed -n 's/^CLOCK=//p' "$STATE")"
    local -a fake=() script=()
    [[ -n "$clock" ]] && fake=(faketime "$clock")
    # F31: every model turn comes from a queue the flow writes (e2e_script_session.py).
    [[ "$(sed -n 's/^SCRIPTED=//p' "$STATE")" == 1 ]] && script=(-E "TUTOR_E2E_SCRIPT=$sandbox/model_script.json")
    model_env "$(sed -n 's/^MODEL=//p' "$STATE")"
    guard_env "$(sed -n 's/^GUARD=//p' "$STATE")" "$clock"
    systemd-run --user --quiet --collect --unit="$SERVER_UNIT" -p RuntimeMaxSec=3600 \
        -p WorkingDirectory="$ROOT" \
        -p StandardOutput="append:$sandbox/server.log" -p StandardError="append:$sandbox/server.log" \
        -E TUTOR_DATA="$sandbox/data" -E TUTOR_KEY="$sandbox/test.key" \
        -E TUTOR_WEBAPP_DIR="$WEB" -E TUTOR_IMAGE_CACHE="$sandbox/cache/images" \
        -E TUTOR_SOURCE_CACHE="$sandbox/cache/sources" -E TUTOR_WIKI_CACHE="$sandbox/cache/wiki" \
        -E TUTOR_ANKI_COLLECTION="$sandbox/cache/none.anki2" -E PATH="$PATH" -E PYTHONPATH="$ROOT:$FOCUS_SRC" \
        -E FOCUS_PROJECT_DATA="$sandbox/focus" -E XDG_STATE_HOME="$sandbox/state" \
        -E TUTOR_THEORY_PHASE="$sandbox/theory_phase.json" -E TUTOR_GUARD_DATA="$sandbox/guard" \
        -E TUTOR_LOCAL_MODEL_URL="${E2E_LOCAL_MODEL_URL:-http://127.0.0.1:9}" \
        -E FAKETIME_DONT_FAKE_MONOTONIC=1 "${MODEL_ENV[@]}" "${GUARD_ENV[@]}" "${script[@]}" \
        "${fake[@]}" "$PY" "$ROOT/scripts/e2e_server.py" --db "$db" --port "$port" --subject "$SUBJECT"
    wait_http "http://127.0.0.1:$port/api/state" 80 || {
        tail -20 "$sandbox/server.log" >&2
        die "server did not start"
    }
    # The worker is serving once its presence beat is in the emulator.
    for _ in {1..30}; do
        [[ "$(curl -sf "$db/tutor/v1-e2e/presence/workers/$dev.json")" != "null" ]] && break
        sleep 0.5
    done
}

# Stop units one by one: a single `systemctl stop a b` enqueues nothing when
# one of them is not loaded, so `restart` used to leave the old server up.
stop_units() {
    local unit
    for unit in "$@"; do
        systemctl --user stop "$unit" 2>/dev/null || true
    done
}
