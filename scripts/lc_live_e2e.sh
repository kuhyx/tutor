#!/bin/bash
# Run one coach request on the real libraries + model in a scratch dir.
# Usage: lc_live_e2e.sh <scratch-dir> <kind> '<json body>'
set -euo pipefail
SCRATCH="$(realpath "$1")"
readonly SCRATCH
REPO="$(cd "$(dirname "$0")/.." && pwd)"
readonly REPO
mkdir -p "$SCRATCH"
[[ -f "$SCRATCH/hmac.key" ]] || head -c 32 /dev/urandom | base64 >"$SCRATCH/hmac.key"
export TUTOR_DATA="$SCRATCH/data" TUTOR_KEY="$SCRATCH/hmac.key"
export TUTOR_SOURCE_CACHE="$SCRATCH/src-cache" FOCUS_PROJECT_DATA="$SCRATCH/focus"
export LEETCODE_COACH_SESSIONS_DIR="$SCRATCH/sessions"
export PYTHONPATH="$REPO"
exec "${LC_E2E_PYTHON:-$REPO/.venv/bin/python}" "$REPO/scripts/lc_live_e2e.py" "${@:2}"
