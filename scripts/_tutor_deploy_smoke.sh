# shellcheck shell=bash
# ============================================================================
# _tutor_deploy_smoke.sh -- tutor_deploy.sh's scratch servers: the baseline
# session (what the live release resumes) and the new release's smoke test.
# Sourced by tutor_deploy.sh; uses its globals (REPO, DATA, LIVE_ROOT, PORT,
# TEMP_DIR, SMOKE_PID, SMOKE_PORT) and helpers (free_port, launch,
# wait_listening, port_pid, session_of, resumable).
# ============================================================================
# shellcheck disable=SC2153,SC2154  # every global here is set by tutor_deploy.sh

# Start release $1 on a scratch port against its own copy of the sessions,
# the subjects and the guard's C3 row; sets SMOKE_PORT and SMOKE_PID. Each
# start gets a fresh copy: startup repairs, backfills and logs a resume.
scratch_server() {
    local release="$1" dir tmp
    SMOKE_PORT="$(free_port)"
    tmp="$(mktemp -d -p "$TEMP_DIR")"
    mkdir -p "$tmp/data"
    for dir in sessions subjects; do
        if [[ -d "$DATA/$dir" ]]; then cp -r "$DATA/$dir" "$tmp/data/"; fi
    done
    head -c 32 /dev/urandom >"$tmp/key"
    # The guard's C3 row, signed with the scratch key. No relay: a temp-data
    # server must never claim real phone requests.
    "$REPO/scripts/scratch_phase.sh" "$tmp/theory_phase.json" "$tmp/key"
    TUTOR_DATA="$tmp/data" TUTOR_KEY="$tmp/key" TUTOR_RELAY=0 \
        TUTOR_THEORY_PHASE="$tmp/theory_phase.json" \
        launch "$release" "$SMOKE_PORT" "$tmp/smoke.log"
    if ! wait_listening "$SMOKE_PORT"; then
        echo "Smoke test: $release did not start:" >&2
        tail -n 20 "$tmp/smoke.log" >&2
        exit 1
    fi
    SMOKE_PID="$(port_pid "$SMOKE_PORT")"
}

stop_scratch() {
    kill "$SMOKE_PID"
    SMOKE_PID=""
}

# The session a restart of the live release would resume: today's newest, but
# only while it can still be taught (C3: the guard may have moved its module
# out of theory since). The live process's own session is not that baseline.
baseline_session() {
    local live="$LIVE_ROOT/current" got
    if [[ ! -d "$live" ]]; then
        resumable "$(session_of "$PORT")"
        return 0
    fi
    scratch_server "$(readlink -f "$live")"
    got="$(session_of "$SMOKE_PORT")"
    stop_scratch
    resumable "$got"
}

# The release must start, resume the same session and serve the web app.
smoke_test() {
    local release="$1" expected="$2" port got
    scratch_server "$release"
    port="$SMOKE_PORT"
    got="$(session_of "$port")"
    if [[ -n "$expected" && "$got" != "$expected" ]]; then
        echo "Smoke test: expected session '$expected', release resumed '$got'" >&2
        exit 1
    fi
    # `/` is only a redirect now; /app/ must serve the build it points at.
    local root
    root="$(curl -s -m 5 -o /dev/null -w '%{http_code} %{redirect_url}' \
        "http://127.0.0.1:$port/")"
    if [[ "$root" != "307 http://127.0.0.1:$port/app/" ]]; then
        echo "Smoke test: / answered '$root', not a redirect to /app/" >&2
        exit 1
    fi
    # Read into a variable: `curl | grep -q` can fail on SIGPIPE under pipefail.
    local page
    page="$(curl -sf -m 5 "http://127.0.0.1:$port/app/" || true)"
    [[ "$page" == *flutter_bootstrap.js* ]] ||
        { echo "Smoke test: /app/ does not serve the web build" >&2; exit 1; }
    curl -sf -m 5 -o /dev/null "http://127.0.0.1:$port/app/main.dart.js" ||
        { echo "Smoke test: /app/main.dart.js is missing" >&2; exit 1; }
    stop_scratch
    echo "Smoke test passed (session '${got:-none}')."
}
