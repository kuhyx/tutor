#!/bin/bash
# ============================================================================
# e2e_evening_gate.sh -- both-sides E2E of `python -m tutor.gate --production
# --evening` on a PRIVATE Xvfb (never :0), scratch HOME, tmp signed ledger and
# key, a fake xdg-open, and a mtime canary on the live tutor ledger.
#
#   up | paid | nox | credit | end | study | study-credit | canary | down
#
# One scenario per call (each < 60 s). Artefacts: $E2E_DIR (default
# ~/data/claude-scratch/e2e/tutor): shots/*.png at 3840x2160, logs.
# ============================================================================

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly REPO_DIR
E2E_DIR="${E2E_DIR:-${HOME}/data/claude-scratch/e2e/tutor}"
readonly E2E_DIR
readonly XNUM="${E2E_XNUM:-73}"
readonly XDISP=":${XNUM}"
readonly LIVE_LEDGER="${HOME}/.local/share/tutor/ledger.json"
readonly DRIVER="${REPO_DIR}/scripts/e2e_evening_driver.py"

log() { printf 'e2e: %s\n' "$1" >&2; }
fail() { printf 'e2e: FAIL %s\n' "$1" >&2; exit 1; }

# The gate as production runs it, in the sandbox: system python, no venv, cwd /.
# PYTHONPATH stands in for the editable install (this checkout, not the live one).
gate_env() {
    env -i PATH="${E2E_DIR}/bin:/usr/bin:/bin" HOME="${E2E_DIR}/home" \
        PYTHONUSERBASE="${HOME}/.local" PYTHONPATH="${REPO_DIR}" \
        XDG_RUNTIME_DIR="${E2E_DIR}/run" TUTOR_DATA="${E2E_DIR}/data" \
        TUTOR_KEY="${E2E_DIR}/hmac.key" E2E_DIR="${E2E_DIR}" DISPLAY="${DISPLAY_FOR_GATE:-$XDISP}" \
        "$@"
}

run_gate() { gate_env env -C / /usr/bin/python3 -m tutor.gate --production --evening; }
driver() { gate_env env -C "${REPO_DIR}" /usr/bin/python3 "$DRIVER" "$@"; }

windows_left() { DISPLAY="$XDISP" xwininfo -root -tree | grep -Ec 'tutor_gate|"tk"|Tk' || true; }

cmd_up() {
    [[ "$XDISP" != ":0" ]] || fail "refusing :0"
    mkdir -p "$E2E_DIR"/{bin,home,run,data,shots,units}
    chmod 700 "$E2E_DIR/run"
    printf 'e2e-test-key-not-the-real-one\n' >"$E2E_DIR/hmac.key"
    rm -f "$E2E_DIR/data/ledger.json" "$E2E_DIR/opened.txt"
    printf '#!/bin/sh\nprintf "%%s\\n" "$1" >> "%s/opened.txt"\n' "$E2E_DIR" >"$E2E_DIR/bin/xdg-open"
    chmod +x "$E2E_DIR/bin/xdg-open"
    stat -c '%Y %s %i' "$LIVE_LEDGER" >"$E2E_DIR/canary.before"
    if [[ ! -S "/tmp/.X11-unix/X${XNUM}" ]]; then
        Xvfb "$XDISP" -screen 0 3840x2160x24 -nolisten tcp >"$E2E_DIR/xvfb.log" 2>&1 &
        echo $! >"$E2E_DIR/xvfb.pid"
        sleep 1.5
    fi
    DISPLAY="$XDISP" xdpyinfo | grep -m1 dimensions
}

reseed() { # <minutes>: a fresh ledger with one row
    rm -f "$E2E_DIR/data/ledger.json"
    [[ "$1" == 0 ]] || driver seed "$1" 1
}

cmd_paid() {
    reseed 60
    local start=$SECONDS code=0
    run_gate || code=$?
    log "paid: exit=${code} in $((SECONDS - start))s, windows left=$(windows_left)"
    [[ $code == 0 && $(windows_left) == 0 ]] || fail "paid must exit 0 with no window"
}

cmd_nox() {
    reseed 5
    local start=$SECONDS code=0
    DISPLAY_FOR_GATE=":89" run_gate || code=$?
    log "no X: exit=${code} in $((SECONDS - start))s"
    [[ $code == 3 ]] || fail "no X must exit 3"
}

cmd_credit() {
    reseed 5
    run_gate >"$E2E_DIR/credit.log" 2>&1 &
    local pid=$!
    sleep 5
    DISPLAY="$XDISP" import -window root "$E2E_DIR/shots/credit-cli-t5.png"
    log "window up: $(windows_left) entries; seeding the full credit"
    local landed=$SECONDS
    driver seed 60 2
    local code=0
    wait "$pid" || code=$?
    log "credit: exit=${code} ${SECONDS}-${landed} = $((SECONDS - landed))s after the row landed"
    [[ $code == 0 ]] || fail "credit must close with 0"
    log "windows left=$(windows_left)"
}

cmd_scenario() { # end | study | study-credit
    reseed 5
    local code=0
    driver "$1" 2>&1 | tee "$E2E_DIR/$1.log" || code=$?
    grep -q '^FAIL' "$E2E_DIR/$1.log" && fail "$1: expectation failed"
    log "$1: $(grep '^EXIT=' "$E2E_DIR/$1.log")  windows left=$(windows_left)"
    return "$code"
}

cmd_canary() {
    local now
    now="$(stat -c '%Y %s %i' "$LIVE_LEDGER")"
    [[ "$now" == "$(cat "$E2E_DIR/canary.before")" ]] || fail "live ledger changed"
    log "canary: live ledger untouched (${now})"
}

cmd_down() {
    if [[ -f "$E2E_DIR/xvfb.pid" ]]; then
        kill "$(cat "$E2E_DIR/xvfb.pid")" 2>/dev/null || true
        rm -f "$E2E_DIR/xvfb.pid"
    fi
}

case "${1:-}" in
    up) cmd_up ;;
    paid) cmd_paid ;;
    nox) cmd_nox ;;
    credit) cmd_credit ;;
    end | study | study-credit) cmd_scenario "$1" ;;
    canary) cmd_canary ;;
    down) cmd_down ;;
    *) fail "usage: $0 up|paid|nox|credit|end|study|study-credit|canary|down" ;;
esac
