#!/bin/bash
# ============================================================================
# Screenshot one screen of the web build on a virtual X display, never on
# kuhy's real one: Chrome --app in its own transient user unit, then
# `import -window root`.
#
# Usage: tool/screenshot.sh <route|-> <WIDTHxHEIGHT> <out.png> [wait_s]
#   route: e.g. /plan/garden (fixture builds take ?screen=<route>); - = Home
# Env: SHOT_DISPLAY (default :97, an Xvfb you started), SHOT_BASE (default
#      http://127.0.0.1:8791/app/), SHOT_PROFILE (scratch Chrome profile).
# Needs: chromium (or google-chrome), ImageMagick `import`, systemd.
# ============================================================================
set -euo pipefail

readonly DISPLAY_ID="${SHOT_DISPLAY:-:97}"
readonly BASE="${SHOT_BASE:-http://127.0.0.1:8791/app/}"
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly APP_DIR
readonly PROFILE="${SHOT_PROFILE:-$APP_DIR/build/screens/profile}"
readonly UNIT="tutor-shot-chrome"

die() { echo "screenshot: $*" >&2; exit 1; }

# The real binaries: /usr/local/bin/<browser> on this PC is a guard wrapper
# (hosts file + extensions) that is not needed for a scratch profile.
browser() {
    local b
    for b in /usr/bin/chromium /usr/bin/google-chrome-stable /opt/google/chrome/chrome; do
        [[ -x "$b" ]] && { echo "$b"; return 0; }
    done
    die "no chromium or google-chrome binary found"
}

stop_chrome() {
    systemctl --user stop "$UNIT" 2>/dev/null || true
}

main() {
    [[ $# -ge 3 ]] || die "usage: $0 <route|-> <WxH> <out.png> [wait_s]"
    local route="$1" size="$2" out="$3" wait_s="${4:-12}" url="$BASE"
    [[ "$size" =~ ^[0-9]+x[0-9]+$ ]] || die "size must be WIDTHxHEIGHT"
    command -v import >/dev/null || die "ImageMagick import missing"
    [[ "$route" != "-" ]] && url="${BASE}?screen=${route}"
    # Own XDG_CONFIG_HOME: Arch's launcher would otherwise read
    # ~/.config/chromium-flags.conf and load kuhy's extensions here.
    mkdir -p "$(dirname "$out")" "$PROFILE" "$PROFILE.xdg"
    stop_chrome
    trap stop_chrome EXIT
    systemd-run --user --quiet --collect --unit="$UNIT" \
        -E DISPLAY="$DISPLAY_ID" -E XDG_CONFIG_HOME="$PROFILE.xdg" \
        "$(browser)" --disable-extensions \
        --app="$url" --user-data-dir="$PROFILE" --no-first-run \
        --no-default-browser-check --password-store=basic \
        --window-position=0,0 --window-size="${size/x/,}" \
        --force-device-scale-factor=1
    sleep "$wait_s"
    DISPLAY="$DISPLAY_ID" import -window root -crop "${size}+0+0" "$out"
    echo "$out"
}

main "$@"
