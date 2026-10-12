#!/bin/bash

# ============================================================================
# Open the Tutor (the +1 h gaming / +60 min shutdown earner).
#
# Opens the desktop app (the Flutter web build in a Chrome --app window) when
# the server serves /app/, else the old page. If the live server answers,
# just open it. Otherwise start tutor.service (the frozen live release, never
# the working tree), installing the unit or deploying a first release when
# missing. The server is the unit, so closing this terminal never kills a
# session mid-block. Clicked from the i3 bar and the control panel too.
# ============================================================================

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly REPO
# tutor.service's port (fixed in systemd/tutor.service).
readonly PORT=8778
readonly UNIT="tutor.service"
readonly URL="http://127.0.0.1:$PORT/"
readonly LIVE_ROOT="$HOME/.local/lib/tutor-live"  # current/ = tutor.service cwd
readonly LOG="$HOME/.local/state/tutor/server.log"
readonly APP_URL="${URL}app/"
# Fixed port (above) and fixed profile: the desktop app's sign-in and its
# offline review queue live in this profile's storage, keyed by origin.
# Changing either silently signs the window out and hides queued reviews.
readonly PROFILE="${TUTOR_DESKTOP_PROFILE:-$HOME/.local/share/tutor-desktop/profile}"
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
        mkdir -p "$PROFILE" "$PROFILE.xdg"
        # --class: the window groups as "tutor", not as the browser. Own
        # XDG_CONFIG_HOME: Arch's launcher would read chromium-flags.conf,
        # whose claude-in-chrome extension opens a sign-in window beside the
        # app (seen on Xvfb). The guard wrapper's extensions still load.
        XDG_CONFIG_HOME="$PROFILE.xdg" setsid -f "$b" --app="$APP_URL" \
            --user-data-dir="$PROFILE" \
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

# The live unit; install.sh installs it (and deploys a first release).
start_server() {
    if ! systemctl --user cat "$UNIT" >/dev/null 2>&1; then
        "$REPO/install.sh"
    elif [[ ! -d "$LIVE_ROOT/current" ]]; then
        echo "No live release yet; deploying one."
        "$REPO/scripts/tutor_deploy.sh"
    else
        systemctl --user start "$UNIT"
    fi
}

main() {
    if is_up; then
        echo "Tutor already running."
    else
        echo "Starting tutor from $(readlink -f "$LIVE_ROOT/current" || echo 'a new release')..."
        start_server
        wait_up || { echo "Tutor did not start; see $LOG" >&2; exit 1; }
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
