#!/bin/bash

# ============================================================================
# Registers the phone app with Google sign-in, then checks it on the phone.
# (Ported from daily-limits/scripts/register_oauth_client.sh.)
#
# The Firebase CLI does the registration: `apps:create ANDROID` adds the
# com.kuhy.tutor app to project kuhy-syncs and `apps:android:sha:create` adds
# the release key's SHA-1. Firebase then creates the matching Android OAuth
# client for that (package, SHA-1) pair. Both steps are idempotent: an app or
# SHA-1 that already exists is left alone, and nothing is deleted or edited.
#
# Without that client, Google sign-in in com.kuhy.tutor fails with
# UNREGISTERED_ON_API_CONSOLE, which Credential Manager surfaces as the far
# less helpful "canceled: account reauth failed".
#
# What this does for you:
#   * derives the SHA-1 from the real release keystore (app/android/
#     key.properties, else ~/.android/release/key.properties) and refuses any
#     key that is not the shared kuhy key;
#   * registers the app and the SHA-1 through the Firebase CLI;
#   * falls back to the console form (opens it, puts each field on the
#     clipboard in form order) only when the CLI is missing or not logged in;
#   * verifies on the phone by reading the app's screen back: the sign-in
#     screen ("Sign in with Google") until the keystore holds a session, the
#     Home screen (its "New subject" card) after. On a phone "Refresh" sits
#     in the overflow menu, so it is no Home marker.
#
# Usage:
#   scripts/register_oauth_client.sh              # register, then verify
#   scripts/register_oauth_client.sh --check      # exit 0 only if registered; no writes
#   scripts/register_oauth_client.sh --sha1       # print the SHA-1 only
#   scripts/register_oauth_client.sh --verify-only
# Needs: keytool, jq, firebase CLI (logged in; else the console fallback).
# ============================================================================

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly REPO_DIR
readonly PROJECT="${TUTOR_FIREBASE_PROJECT:-kuhy-syncs}"
# shellcheck disable=SC2034  # read by the sourced _register_oauth_client_console.sh
readonly CONSOLE_URL="https://console.cloud.google.com/auth/clients?project=${PROJECT}"
readonly PACKAGE="com.kuhy.tutor"
readonly CLIENT_NAME="tutor"
readonly DEVICE="${ADB_SERIAL:-23181JEGR08034}"
readonly CANONICAL_SHA256="9D:CC:2E:6C:05:3C:44:BB:05:07:90:3B:9D:D3:51:01:5E:A7:D4:31:5B:6E:E6:C8:53:DD:8D:80:7B:98:F8:46"

log() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }
step() { printf '   %s\n' "$1"; }
die() {
    echo "error: $1" >&2
    exit 1
}

# clip, pause, register_in_console.
# shellcheck source-path=SCRIPTDIR source=_register_oauth_client_console.sh
source "$(dirname "${BASH_SOURCE[0]}")/_register_oauth_client_console.sh"

# The repo's own key.properties wins; the shared one is the fallback.
key_properties() {
    local candidate
    for candidate in "$REPO_DIR/app/android/key.properties" \
        "$HOME/.android/release/key.properties"; do
        if [[ -f "$candidate" ]]; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    die "no key.properties in $REPO_DIR/app/android or ~/.android/release"
}

# Reads one key out of key.properties.
prop() { sed -n "s/^$1=//p" "$2" | head -1; }

# Prints one fingerprint line (SHA1 or SHA256) of the release key. The
# password goes through the environment, so it never shows in `ps`.
fingerprint() {
    local properties store alias
    properties="$(key_properties)"
    store="$(prop storeFile "$properties")"
    alias="$(prop keyAlias "$properties")"
    [[ "$store" = /* ]] || store="$(dirname "$properties")/$store"
    KS_PASS="$(prop storePassword "$properties")" \
        keytool -list -v -keystore "$store" -alias "$alias" \
        -storepass:env KS_PASS 2>/dev/null |
        sed -n "s/^[[:space:]]*$1:[[:space:]]*//p" | head -1 | tr -d ' \r'
}

# Refuses a keystore that is not the shared kuhy release key: a client
# registered with any other SHA-1 would never match the installed APK.
# Prints the SHA-1 as the console shows it (AA:BB:...).
release_sha1() {
    local sha256 sha1
    sha256="$(fingerprint SHA256)"
    [[ "$sha256" == "$CANONICAL_SHA256" ]] ||
        die "keystore SHA-256 '$sha256' is not the shared kuhy key"
    sha1="$(fingerprint SHA1)"
    [[ -n "$sha1" ]] || die "could not read a SHA-1 from the keystore"
    printf '%s\n' "$sha1"
}

# Firebase wants the SHA-1 as 40 lowercase hex digits, no colons.
sha_hex() { tr -d ':' <<<"$1" | tr 'A-F' 'a-f'; }

# Prints why the Firebase CLI cannot be used, or nothing when it can.
cli_problem() {
    if ! command -v firebase >/dev/null 2>&1; then
        echo "the Firebase CLI is not installed"
    elif ! timeout 50 firebase login:list --json 2>/dev/null |
        sed -n '/^{/,$p' | jq -e '(.result // []) | length > 0' >/dev/null; then
        echo "the Firebase CLI is not logged in (firebase login)"
    fi
}

# Runs one firebase call and prints its JSON. On failure the error carries
# firebase's own message, e.g. a SHA-1 already held by another client.
fb() {
    local out err
    err="$(mktemp)"
    if ! out="$(timeout 50 firebase "$@" --project "$PROJECT" --json 2>"$err")"; then
        local reason
        reason="$(tail -5 "$err"; sed -n '/^{/,$p' <<<"$out" | jq -r '.error.message? // empty' 2>/dev/null)"
        rm -f "$err"
        die "firebase $1 failed: ${reason:-no output}"
    fi
    rm -f "$err"
    sed -n '/^{/,$p' <<<"$out"
}

app_id() {
    fb apps:list ANDROID | jq -r --arg p "$PACKAGE" \
        '[.result[]? | select(.packageName == $p) | .appId][0] // empty'
}

sha_registered() {
    fb apps:android:sha:list "$1" | jq -e --arg s "$2" \
        '[.result[]? | .shaHash | ascii_downcase | gsub(":"; "")] | index($s)' >/dev/null
}

# --check: exit 0 only if the app and the SHA-1 are both registered. It never
# writes and never falls back to the console.
check() {
    local sha problem id
    sha="$(sha_hex "$(release_sha1)")"
    problem="$(cli_problem)"
    [[ -z "$problem" ]] || die "$problem"
    id="$(app_id)"
    [[ -n "$id" ]] || die "$PACKAGE is not registered in $PROJECT"
    sha_registered "$id" "$sha" || die "the release SHA-1 is not registered on $PACKAGE"
    echo "$PACKAGE and its release SHA-1 are registered in $PROJECT as $id"
}

# Adds only what is missing: the app, then the SHA-1.
register_with_cli() {
    local sha id
    sha="$(sha_hex "$1")"
    id="$(app_id)"
    if [[ -z "$id" ]]; then
        log "Creating Firebase app $PACKAGE in $PROJECT"
        fb apps:create ANDROID "$CLIENT_NAME" --package-name "$PACKAGE" >/dev/null
        id="$(app_id)"
        [[ -n "$id" ]] || die "apps:create succeeded but $PACKAGE is not listed"
    fi
    if ! sha_registered "$id" "$sha"; then
        log "Registering the release SHA-1 on $PACKAGE"
        fb apps:android:sha:create "$id" "$sha" >/dev/null
    fi
    log "$PACKAGE registered as $id"
    step "Firebase creates the OAuth client; it takes a few minutes to work."
}

register() {
    local sha1 problem
    sha1="$(release_sha1)"
    problem="$(cli_problem)"
    if [[ -z "$problem" ]]; then
        register_with_cli "$sha1"
    else
        log "Console fallback: $problem."
        register_in_console "$sha1"
    fi
    verify_on_phone
}

# Flutter exposes Text and tooltips as content-desc, plain views as text.
has_label() { grep -qE "(text|content-desc)=\"[^\"]*$1" "$2"; }

# Launches the app and reads its screen. The home screen asks the keystore
# for a session, so a revoked one shows as signed out, not a stale flag.
verify_on_phone() {
    log "Verifying on the phone"
    if ! adb devices | grep -q "^$DEVICE"; then
        step "phone not attached; reconnect it and rerun with --verify-only"
        return 1
    fi
    local dump
    dump="$(mktemp --suffix=.xml)"
    adb -s "$DEVICE" shell am start -n "$PACKAGE/.MainActivity" >/dev/null 2>&1
    sleep 6
    adb -s "$DEVICE" shell uiautomator dump /sdcard/tutor_ui.xml >/dev/null 2>&1
    adb -s "$DEVICE" pull /sdcard/tutor_ui.xml "$dump" >/dev/null 2>&1
    if has_label "Sign in with Google" "$dump"; then
        log "NOT SIGNED IN yet."
        step "Tap 'Sign in with Google' and pick the sync account."
        step "An error under the button names the cause (screen dump: $dump)."
        step "Then rerun: scripts/register_oauth_client.sh --verify-only"
        return 1
    fi
    if has_label "New subject" "$dump"; then
        rm -f "$dump"
        log "SIGNED IN: the Home screen is showing."
        return 0
    fi
    log "Neither the sign-in nor the Home screen is showing."
    step "Is the app in front (focus-mode hidden?) Screen dump: $dump"
    return 1
}


main() {
    case "${1:-}" in
        --verify-only) verify_on_phone ;;
        --check) check ;;
        --sha1) release_sha1 ;;
        "") register ;;
        *)
            echo "usage: $0 [--check|--sha1|--verify-only]" >&2
            exit 2
            ;;
    esac
}

main "$@"
