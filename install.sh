#!/bin/bash

# ============================================================================
# Install the live tutor as a persistent user service (tutor.service): the
# desktop web app on 127.0.0.1:8778/app/ plus the Firebase relay the phone
# and that app talk to.
# Enabled under default.target (linger is on), so it is back after every
# reboot or curfew shutdown. Writes only under $HOME, except the pacman
# install of the model sandbox's bwrap + pasta when missing. Rerunnable.
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
readonly BIN_DIR="${TUTOR_BIN_DIR:-$HOME/.local/bin}"

log() { printf 'tutor install: %s\n' "$*"; }

# The unit runs the repo venv; the relay needs crdt-sync (>= 0.10: e2e, with
# pynacl + argon2-cffi) and httpx in it.
ensure_venv() {
    if ! "$REPO/.venv/bin/python" -c 'from crdt_sync import unlock_e2e; import nacl, argon2, httpx' 2>/dev/null; then
        log "setting up the venv"
        "$REPO/scripts/setup_dev.sh"
    fi
}

# The tutor model's CLI runs in bubblewrap behind pasta and an nftables fence
# (scripts/tutor_model_sandbox.sh, tutor_model_netfence.sh; ip and jq read
# the host's addresses); without them every turn fails.
ensure_sandbox_tools() {
    local tool
    for tool in bwrap pasta nft ip jq; do
        if ! command -v "$tool" >/dev/null; then
            log "installing bubblewrap, passt, nftables, iproute2, jq (the model sandbox)"
            sudo pacman -S --needed --noconfirm bubblewrap passt nftables iproute2 jq
            return
        fi
    done
}

install_unit() {
    mkdir -p "$UNIT_DIR" "$LOG_DIR"
    install -m 644 "$REPO/systemd/$UNIT" "$UNIT_DIR/$UNIT"
    systemctl --user daemon-reload
    systemctl --user enable --quiet "$UNIT"
    log "$UNIT $(systemctl --user is-enabled "$UNIT")"
}

# `tutor` in any terminal opens the app: a wrapper (not a symlink: run.sh finds
# its repo from its own path) that runs the live release's run.sh, which the
# deploy keeps current, so it never points into a working tree or worktree.
install_launcher() {
    mkdir -p "$BIN_DIR"
    printf '%s\n' '#!/bin/bash' \
        "exec \"$LIVE_ROOT/current/run.sh\" \"\$@\"" >"$BIN_DIR/tutor"
    chmod 755 "$BIN_DIR/tutor"
    log "launcher $BIN_DIR/tutor"
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
    if [[ "${1:-}" == --launcher-only ]]; then
        install_launcher
        return
    fi
    command -v systemctl >/dev/null || { log "systemctl is required"; exit 1; }
    ensure_venv
    ensure_sandbox_tools
    install_unit
    install_launcher
    start_unit
}

main "$@"
