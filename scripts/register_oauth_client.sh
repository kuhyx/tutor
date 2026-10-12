#!/bin/bash

# ============================================================================
# Walks the one step that cannot be automated -- registering the phone app's
# Android OAuth client -- and runs everything around it that can be.
# (Ported from daily-limits/scripts/register_oauth_client.sh.)
#
# Why a human has to click: an OAuth client is a credential and Google
# exposes no create API for one. Neither gcloud nor the Firebase CLI has a
# command; the console is the only path.
#
# Until it exists, Google sign-in in com.kuhy.tutor fails with
# UNREGISTERED_ON_API_CONSOLE, which Credential Manager surfaces as the far
# less helpful "canceled: account reauth failed".
#
# What this does for you:
#   * derives the SHA-1 from the real release keystore (app/android/
#     key.properties), so the pasted value cannot be a stale copy;
#   * opens the console and puts each field on the clipboard in form order;
#   * verifies on the phone by reading the app's screen back: the sign-in
#     screen ("Sign in with Google") until the keystore holds a session, the
#     Home screen (its "Refresh" button) after.
#
# Usage:
#   scripts/register_oauth_client.sh              # register, then verify
#   scripts/register_oauth_client.sh --sha1       # print the SHA-1 only
#   scripts/register_oauth_client.sh --verify-only
# ============================================================================

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly REPO_DIR
readonly CONSOLE_URL="https://console.cloud.google.com/auth/clients?project=kuhy-syncs"
readonly PACKAGE="com.kuhy.tutor"
readonly CLIENT_NAME="tutor"
readonly DEVICE="${ADB_SERIAL:-23181JEGR08034}"
readonly CANONICAL_SHA256="9D:CC:2E:6C:05:3C:44:BB:05:07:90:3B:9D:D3:51:01:5E:A7:D4:31:5B:6E:E6:C8:53:DD:8D:80:7B:98:F8:46"

log() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }
step() { printf '   %s\n' "$1"; }

# Copies to the clipboard when a tool is available; prints regardless, so this
# still works over ssh with no X display.
clip() {
    if command -v xclip >/dev/null 2>&1; then
        printf '%s' "$1" | xclip -selection clipboard 2>/dev/null || true
        printf '   \033[32m[copied]\033[0m %s\n' "$1"
    else
        printf '   %s\n' "$1"
    fi
}

pause() { read -rp "   ...press Enter when that field is filled " _; }

# Reads one key out of key.properties.
prop() {
    grep -E "^$1=" "$2" | cut -d= -f2-
}

# Prints one fingerprint line (SHA1 or SHA256) of the release key.
fingerprint() {
    local properties="$REPO_DIR/app/android/key.properties"
    if [[ ! -f "$properties" ]]; then
        echo "error: $properties not found; cp ~/.android/release/key.properties there" >&2
        return 1
    fi
    local store password alias
    store="$(prop storeFile "$properties")"
    password="$(prop storePassword "$properties")"
    alias="$(prop keyAlias "$properties")"
    [[ "$store" = /* ]] || store="$REPO_DIR/app/android/$store"
    keytool -list -v -keystore "$store" -alias "$alias" \
        -storepass "$password" 2>/dev/null |
        grep -E "^[[:space:]]*$1:" | head -1 | sed "s/.*$1: //" | tr -d ' \r'
}

# Refuses a keystore that is not the shared kuhy release key: a client
# registered with any other SHA-1 would never match the installed APK.
release_sha1() {
    local sha256
    sha256="$(fingerprint SHA256)"
    if [[ "$sha256" != "$CANONICAL_SHA256" ]]; then
        echo "error: keystore SHA-256 '$sha256' is not the shared kuhy key" >&2
        return 1
    fi
    fingerprint SHA1
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
    if has_label "Refresh" "$dump"; then
        rm -f "$dump"
        log "SIGNED IN: the Home screen is showing."
        return 0
    fi
    log "Neither the sign-in nor the Home screen is showing."
    step "Is the app in front (focus-mode hidden?) Screen dump: $dump"
    return 1
}

register() {
    local sha1
    sha1="$(release_sha1)"
    if [[ -z "$sha1" ]]; then
        echo "error: could not read a SHA-1 from the keystore" >&2
        exit 1
    fi

    log "Register ONE Android OAuth client in project kuhy-syncs"
    step "Google has no API for this. One form, three fields."
    if command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$CONSOLE_URL" >/dev/null 2>&1 &
    else
        step "$CONSOLE_URL"
    fi
    sleep 2

    step "Click '+ CREATE CLIENT', set Application type = Android."
    step "Field 'Name':"
    clip "$CLIENT_NAME"
    pause
    step "Field 'Package name':"
    clip "$PACKAGE"
    pause
    step "Field 'SHA-1 certificate fingerprint':"
    clip "$sha1"
    pause
    step "Click CREATE. Do NOT touch the existing Web client: it is the"
    step "audience the app's tokens are minted for (kGoogleServerClientId)."
    read -rp "   Propagation takes a few minutes. Install the APK, sign in on the phone, then Enter: " _
    verify_on_phone
}

main() {
    case "${1:-}" in
        --verify-only) verify_on_phone ;;
        --sha1) release_sha1 ;;
        "") register ;;
        *)
            echo "usage: $0 [--verify-only|--sha1]" >&2
            exit 2
            ;;
    esac
}

main "$@"
