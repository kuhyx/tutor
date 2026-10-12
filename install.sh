#!/bin/bash

# ============================================================================
# Install the live tutor as a persistent user service (tutor.service): the
# web page on 127.0.0.1:8778 plus the Firebase relay the phone talks to.
# Enabled under default.target (linger is on), so it is back after every
# reboot or curfew shutdown. Writes only under $HOME. Rerunnable.
#
# It never restarts a running server (that is scripts/tutor_deploy.sh's job,
# after a reply finishes), and never starts one while anything else holds the
# port (the deploy hands an older server over).
# ============================================================================

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly REPO
readonly UNIT="tutor.service"
readonly UNIT_DIR="$HOME/.config/systemd/user"
readonly LIVE_ROOT="$HOME/.local/lib/tutor-live"
readonly LOG_DIR="$HOME/.local/state/tutor"
readonly PORT=8778

log() { printf 'tutor install: %s\n' "$*"; }

# The unit runs the repo venv; the relay needs crdt-sync and httpx in it.
ensure_venv() {
    if ! "$REPO/.venv/bin/python" -c 'import crdt_sync, httpx' 2>/dev/null; then
        log "setting up the venv"
        "$REPO/scripts/setup_dev.sh"
    fi
}

install_unit() {
    mkdir -p "$UNIT_DIR" "$LOG_DIR"
    install -m 644 "$REPO/systemd/$UNIT" "$UNIT_DIR/$UNIT"
    systemctl --user daemon-reload
    systemctl --user enable --quiet "$UNIT"
    log "$UNIT $(systemctl --user is-enabled "$UNIT")"
}

start_unit() {
    if [[ ! -d "$LIVE_ROOT/current" ]]; then
        log "no live release yet; deploying one"
        "$REPO/scripts/tutor_deploy.sh"
    elif systemctl --user is-active --quiet "$UNIT"; then
        log "$UNIT already running (pid $(systemctl --user show -p MainPID --value "$UNIT"))"
    elif ! "$REPO/scripts/tutor_port_free.sh" "$PORT" 2>/dev/null; then
        log ":$PORT is served outside $UNIT; scripts/tutor_deploy.sh hands it over"
    else
        systemctl --user start "$UNIT"
        log "$UNIT started"
    fi
}

main() {
    command -v systemctl >/dev/null || { log "systemctl is required"; exit 1; }
    ensure_venv
    install_unit
    start_unit
}

main "$@"
