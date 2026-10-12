#!/bin/bash

# ============================================================================
# Scripted tutor run: a simulated know-nothing learner drives the real tutor
# over HTTP against a SANDBOXED data dir and ledger key (no real gaming time
# is minted), then the transcript is adjudicated by code. The server is left
# running only until the end. (The old page's screenshots went with the page
# on 2026-10-12; the Flutter client has its own: CLAUDE.md "app screenshots".)
# ============================================================================

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
readonly ROOT
readonly RUN="$ROOT/build/tutor-run"
readonly PORT="${TUTOR_PORT:-8779}"
readonly PY="$ROOT/.venv/bin/python"
SERVER_PID=""

cleanup() {
    if [[ -n "$SERVER_PID" ]]; then
        kill "$SERVER_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT

mkdir -p "$RUN/data" "$ROOT/build/tutor-run-out"
rm -rf "${RUN:?}/data"
mkdir -p "$RUN/data"
head -c 32 /dev/urandom | base64 > "$RUN/test.key"
export TUTOR_DATA="$RUN/data"
export TUTOR_KEY="$RUN/test.key"

"$PY" -m tutor --port "$PORT" --simulate-time 2> "$RUN/server.log" &
SERVER_PID=$!
for _ in {1..40}; do
    curl -sf "http://127.0.0.1:$PORT/api/state" > /dev/null && break
    sleep 0.5
done

"$PY" -m tutor.scripted --url "http://127.0.0.1:$PORT" "$@"

session="$(ls -t "$RUN"/data/sessions/*.jsonl | head -1)"
cp "$session" "$ROOT/build/tutor-run-out/transcript.jsonl"
"$PY" -m tutor.adjudicate "$session" | tee "$ROOT/build/tutor-run-out/adjudication.txt" || true

echo "transcript and adjudication in $ROOT/build/tutor-run-out/"
