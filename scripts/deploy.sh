#!/bin/bash
# ============================================================================
# One-command deploy: build the desktop web app, then put the repo live with
# tutor_deploy.sh (fresh release, smoke test, wait for idle, restart
# tutor.service). Idempotent; exits non-zero unless the smoke test passes.
# The phone app ships through CI-signed release APKs, not from here.
# ============================================================================
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
readonly REPO

(cd "$REPO/app" && fvm flutter build web --release --base-href /app/)
exec "$REPO/scripts/tutor_deploy.sh" "$@"
