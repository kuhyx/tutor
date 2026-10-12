#!/bin/bash

# ============================================================================
# Sets the five GitHub secrets .github/workflows/release-apk.yml needs, from
# the local sources of truth, so no value is ever retyped or pasted:
#
#   ANDROID_KEYSTORE_BASE64     base64 of the shared .jks (from key.properties)
#   ANDROID_KEYSTORE_PASSWORD   } app/android/key.properties (gitignored;
#   ANDROID_KEY_ALIAS           } a copy of ~/.android/release/key.properties)
#   ANDROID_KEY_PASSWORD        }
#   TUTOR_FIREBASE_JSON         {apiKey,databaseUrl,uid} of
#                               ~/.config/crdt-sync/firebase.json plus
#                               webClientId from app/lib/config/firebase_local.dart
#
# Values go to `gh secret set` on stdin, never on the command line.
#
# Usage:
#   scripts/set_release_secrets.sh             # set all five on kuhyx/tutor
#   scripts/set_release_secrets.sh --dry-run   # names + lengths only
# Needs: gh (logged in), jq, base64.
# ============================================================================

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly REPO_DIR
readonly GH_REPO="kuhyx/tutor"
readonly PROPS="$REPO_DIR/app/android/key.properties"
readonly LOCAL_DART="$REPO_DIR/app/lib/config/firebase_local.dart"
readonly FIREBASE_JSON="$HOME/.config/crdt-sync/firebase.json"

die() { printf 'error: %s\n' "$1" >&2; exit 1; }

prop() { grep -E "^$1=" "$PROPS" | cut -d= -f2-; }

# The Web client id as the app was compiled with it. The generated file wraps
# long literals onto the next line, so join lines before matching.
web_client_id() {
    tr -d '\n' < "$LOCAL_DART" |
        grep -oE "kGoogleServerClientId =[[:space:]]*'[^']+'" |
        sed -E "s/.*'([^']+)'/\1/"
}

firebase_json() {
    jq -c --arg web "$1" '{apiKey, databaseUrl, uid, webClientId: $web}' \
        "$FIREBASE_JSON"
}

# put NAME VALUE: sets one secret, or reports its length on --dry-run.
put() {
    [[ -n "$2" ]] || die "$1 would be empty; refusing"
    if [[ "$DRY_RUN" == 1 ]]; then
        printf '   %-26s %s chars\n' "$1" "${#2}"
    else
        printf '%s' "$2" | gh secret set "$1" -R "$GH_REPO"
    fi
}

main() {
    DRY_RUN=0
    case "${1:-}" in
        --dry-run) DRY_RUN=1 ;;
        "") ;;
        *) die "usage: $0 [--dry-run]" ;;
    esac
    [[ -f "$PROPS" ]] || die "$PROPS missing (cp ~/.android/release/key.properties there)"
    [[ -f "$LOCAL_DART" ]] || die "$LOCAL_DART missing (cd app && dart run tool/write_firebase_config.dart)"
    [[ -f "$FIREBASE_JSON" ]] || die "$FIREBASE_JSON missing"

    local store web
    store="$(prop storeFile)"
    [[ -f "$store" ]] || die "keystore $store not found"
    web="$(web_client_id)"
    [[ -n "$web" ]] || die "no kGoogleServerClientId in $LOCAL_DART"

    put ANDROID_KEYSTORE_BASE64 "$(base64 -w0 "$store")"
    put ANDROID_KEYSTORE_PASSWORD "$(prop storePassword)"
    put ANDROID_KEY_ALIAS "$(prop keyAlias)"
    put ANDROID_KEY_PASSWORD "$(prop keyPassword)"
    put TUTOR_FIREBASE_JSON "$(firebase_json "$web")"
    [[ "$DRY_RUN" == 1 ]] || gh secret list -R "$GH_REPO"
}

main "$@"
