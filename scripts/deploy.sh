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

# Same JS as a plain `build web --release --base-href /app/`, minus work that
# only costs time: pub get runs once as its own step (--no-pub), and the wasm
# dry run (compiles wasm to a scratch dir, prints warnings, writes no output)
# is off. Under machine load the plain build overran 60 s.
"$REPO/scripts/check_web_build_config.sh" --source-only "$REPO/app"
(cd "$REPO/app" && fvm flutter pub get)
(cd "$REPO/app" && fvm flutter build web --release --no-pub --no-wasm-dry-run --base-href /app/)
exec "$REPO/scripts/tutor_deploy.sh" "$@"
