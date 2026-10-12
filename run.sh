#!/bin/bash

# ============================================================================
# Open the Tutor (the +1 h gaming / +60 min shutdown earner).
#
# Opens the desktop app (the Flutter web build in a Chrome --app window) when
# the server serves /app/, else the old page. If the live server answers,
# just open it. Otherwise start it from the frozen
# live release (never the working tree), deploying one first if none exists.
# The server is detached, so closing this terminal never kills a session
# mid-block. Clicked from the i3 bar and the control panel too.
# ============================================================================

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly REPO
readonly PORT="${TUTOR_PORT:-8778}"
readonly URL="http://127.0.0.1:$PORT/"
readonly LIVE_ROOT="${TUTOR_LIVE_ROOT:-$HOME/.local/lib/tutor-live}"
readonly LOG_DIR="${TUTOR_LOG_DIR:-$HOME/.local/state/tutor}"
readonly APP_URL="${URL}app/"
# Fixed port (above) and fixed profile: the desktop app's sign-in and its
# offline review queue live in this profile's storage, keyed by origin.
# Changing either silently signs the window out and hides queued reviews.
readonly PROFILE="${TUTOR_DESKTOP_PROFILE:-$HOME/.local/share/tutor-desktop/profile}"
# The card editor writes here (the repo deck), not only into the release copy.
readonly DECK_SRC="${TUTOR_DECK_SRC:-$REPO/subjects/automation/deck}"
OPEN=1

usage() {
    echo "Usage: $(basename "$0") [--no-open]"
    echo "  --no-open   start the tutor if needed and print its URL only"
    exit 0
}

# The Flutter web app, when the running server has it built and mounted.
app_up() {
    curl -sf -m 2 -o /dev/null "$APP_URL"
}

# chromium on this PC (google-chrome-stable as a fallback); TUTOR_BROWSER wins.
browser() {
    local b
    for b in "${TUTOR_BROWSER:-}" chromium google-chrome-stable; do
        [[ -n "$b" ]] && command -v "$b" >/dev/null && { echo "$b"; return 0; }
    done
    return 1
}

open_ui() {
    local b
    if app_up && b="$(browser)"; then
        mkdir -p "$PROFILE"
        # --class: the window groups as "tutor", not as the browser.
        setsid -f "$b" --app="$APP_URL" --user-data-dir="$PROFILE" \
            --class=tutor --password-store=basic --no-first-run \
            >/dev/null 2>&1
    else
        # Old page until the release ships the web app (or no browser).
        setsid -f xdg-open "$URL" >/dev/null 2>&1
    fi
}

is_up() {
    curl -sf -m 2 "${URL}api/state" >/dev/null
}

wait_up() {
    local _
    for _ in {1..40}; do
        is_up && return 0
        sleep 0.5
    done
    return 1
}

# Same detached launch as scripts/tutor_deploy.sh, from the current release.
start_server() {
    if [[ ! -d "$LIVE_ROOT/current" ]]; then
        echo "No live release yet; deploying one."
        "$REPO/scripts/tutor_deploy.sh" --port "$PORT"
        return
    fi
    mkdir -p "$LOG_DIR"
    TUTOR_DECK_SRC="$DECK_SRC" "$REPO/scripts/tutor_launch.sh" \
        "$LIVE_ROOT/current" "$PORT" "$LOG_DIR/server.log"
}

main() {
    if is_up; then
        echo "Tutor already running."
    else
        echo "Starting tutor from $(readlink -f "$LIVE_ROOT/current" || echo 'a new release')..."
        start_server
        wait_up || { echo "Tutor did not start; see $LOG_DIR/server.log" >&2; exit 1; }
    fi
    echo "Tutor: $URL"
    if [[ $OPEN -eq 1 ]]; then
        open_ui
    fi
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --no-open) OPEN=0; shift ;;
        -h | --help) usage ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

main
