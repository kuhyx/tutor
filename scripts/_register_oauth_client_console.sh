# shellcheck shell=bash
# ============================================================================
# The console fallback of scripts/register_oauth_client.sh: used only when the
# Firebase CLI is missing or not logged in. Sourced only by that script, which
# defines PROJECT, CONSOLE_URL, PACKAGE, CLIENT_NAME, log() and step() first.
# ============================================================================
# shellcheck disable=SC2154  # every global here is set by register_oauth_client.sh

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

# The manual fallback: one console form, three fields.
register_in_console() {
    local sha1="$1"
    log "Register ONE Android OAuth client in project $PROJECT"
    step "One form, three fields."
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
}
