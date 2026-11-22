#!/bin/bash
# ============================================================================
# Refuse a web release without the real Firebase identifiers. With empty ones
# the app paints one error glyph on every route (2026-11-22 15:09: a fresh
# worktree's `e2e_sandbox.sh` had written the --placeholder
# lib/config/firebase_local.dart, and the deploy shipped a build from it).
#
# Usage: check_web_build_config.sh [--source-only] <app-dir>
#   default       the config file is real AND build/web/main.dart.js carries
#                 its database URL (tutor_deploy.sh, before copying)
#   --source-only just the config file (deploy.sh, before the 45 s build)
# Exit 0 = fine, 1 = refused (the reason and the fix on stderr).
# ============================================================================
set -euo pipefail

source_only=0
if [[ "${1:-}" == "--source-only" ]]; then
    source_only=1
    shift
fi
[[ $# -eq 1 ]] || { echo "usage: $0 [--source-only] <app-dir>" >&2; exit 2; }
readonly APP="$1"
readonly LOCAL="$APP/lib/config/firebase_local.dart"
readonly BUNDLE="$APP/build/web/main.dart.js"
readonly FIX="run: (cd $APP && fvm dart run tool/write_firebase_config.dart), then rebuild"

refuse() { echo "Refusing the release: $*; $FIX" >&2; exit 1; }

[[ -f "$LOCAL" ]] || refuse "$LOCAL is missing"
# The value may sit on the line after the `=`, so join the lines first.
url="$(tr '\n' ' ' <"$LOCAL" |
    sed -n "s/.*kFirebaseDatabaseUrl *= *'\([^']*\)'.*/\1/p")"
[[ -n "$url" ]] || refuse "$LOCAL has no database URL (a placeholder?)"
((source_only)) && exit 0
[[ -f "$BUNDLE" ]] || refuse "no web bundle at $BUNDLE"
grep -qF -- "$url" "$BUNDLE" ||
    refuse "the web bundle was built without the Firebase identifiers"
