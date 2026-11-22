#!/bin/bash
# ============================================================================
# Agent E2E sandbox: the real web build and the real engine + relay, against
# a COPY of the data dir and a local Firebase RTDB emulator. Never the live
# data dir, ledger, RTDB, device id, :8778 or tutor.service. Each command
# stays under 60 s; the emulator and the server run as transient user units.
#
# Usage:
#   scripts/e2e_sandbox.sh build              # e2e web build (once per app change)
#   scripts/e2e_sandbox.sh up [--as-of "YYYY-MM-DD HH:MM[:SS]"]
#                                    # fresh sandbox; --as-of rewinds the copy
#                                    # (e2e_prepare.py)
#        [--struggle] [--carry N]   # F5: seed 2 Again; F6: N signed minutes
#        [--nocard due|review]      # F12: no card left (reviews due / module review)
#        [--gate]                   # F21: the next module waits on 2 unpassed cards
#        [--learn S/M]              # F22: one untaught card left in module M of S
#        [--unit-gate fresh|taught] # F28: LC on day one, or prefix-sums taught
#        [--phase "MODE [S/M ...]"] # the guard's C3 row (default missing)
#        [--guard-theory JSON]      # canned /api/theory "theory" map (default: down)
#        [--unarchive S]            # F24: kuhy archived SQL; teach it here
#        [--rework S/M/SLUG]        # F29: guard history of SLUG; module M done
#        [--model-down network|refuse]  # F14: every Claude call fails: no route
#                                    # (an outage) or a 400 stub (a model error)
#                                    # the day before; --as-of runs the
#                                    # worker under libfaketime from then
#   scripts/e2e_sandbox.sh flow F1|F3..F26|F28|F29 [PHASE]
#                                    # drive one flow; exit 0 = PASS. A tutor
#                                    # turn can outlast 60 s, so F1/F3/F4/F5
#                                    # run as send, wait (75 = still pending:
#                                    # call it again), check (e2e_drive.py)
#   scripts/e2e_sandbox.sh restart [--model-down network|refuse|none]
#                                    # F6 again: a second worker start; F14
#                                    # switches how Claude fails in between
#   scripts/e2e_sandbox.sh hold               # F16: no worker; the app served statically
#   scripts/e2e_sandbox.sh phase theory S/M.. | solve | bad S/M | missing
#                                    # rewrite the sandbox's C3 row (F22-F26)
#   scripts/e2e_sandbox.sh down               # stop units, delete the sandbox
# Env: E2E_SUBJECT, E2E_CARD (the card a flow must start), E2E_DISPLAY (:97),
# E2E_SESSION (F3/F4: the session at card end; up --as-of "2026-10-20 17:24:30").
# The app talks to the emulator over plain HTTP/1.1, as to the real database
# (which never negotiates h2): Chrome's 6 connections per host are the real
# budget, and the app keeps at most 4 streams (DOCS-contract §9).
# Needs: java + the cached RTDB emulator jar (firebase-tools), chromium, an
# Xvfb on E2E_DISPLAY, fvm, faketime (libfaketime) for --as-of.
# ============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly ROOT
readonly PY="$ROOT/.venv/bin/python"
# This checkout's tutor package, not whatever the venv's editable install names.
export PYTHONPATH="$ROOT"
readonly STATE="$ROOT/build/e2e-sandbox/state"
readonly SCREENS="$ROOT/app/build/screens"
readonly WEB="$ROOT/app/build/web_e2e"
readonly SRC_DATA="$HOME/.local/share/tutor"
readonly SUBJECT="${E2E_SUBJECT:-chc-rozumie-poj-cia-z-maila-do-centrum}"
readonly CARD="${E2E_CARD:-vhost-what}"
readonly SESSION="${E2E_SESSION:-20261020-172115-3f84}"
readonly DISPLAY_ID="${E2E_DISPLAY:-:97}"
# Unit names carry this checkout's tag: parallel worktrees each run their
# own sandbox, and one's `down` never stops another's.
TAG="$(printf '%s' "$ROOT" | md5sum | cut -c1-8)"
readonly TAG
readonly DB_UNIT="tutor-e2e-db-$TAG"
readonly SERVER_UNIT="tutor-e2e-server-$TAG"
readonly MODEL_UNIT="tutor-e2e-model-$TAG"
readonly HOLD_UNIT="tutor-e2e-hold-$TAG"
# focus_project (F7-F10) lives outside this repo; its data dir is the sandbox's.
# shellcheck disable=SC2034  # read by the sourced _e2e_sandbox_units.sh
readonly FOCUS_SRC="${E2E_FOCUS_SRC:-$HOME/src/utils/focus_project}"

die() { echo "e2e_sandbox: $*" >&2; exit 1; }

# free_port, wait_http, emulator_jar, model_env, start_server.
# shellcheck source-path=SCRIPTDIR source=_e2e_sandbox_units.sh
source "$(dirname "${BASH_SOURCE[0]}")/_e2e_sandbox_units.sh"

# The e2e build must fit one 60 s call. A full release build (wasm dry run,
# -O4, source maps, icon tree shaking) took 50-70 s under the cap; these
# flags cut it to ~36 s and change nothing a flow asserts. The stamp skips
# the compile entirely when no input of the build changed.
readonly BUILD_FLAGS=(--release --no-pub -O1 --no-wasm-dry-run --no-source-maps
    --no-tree-shake-icons -t tool/e2e/main.dart -o build/web_e2e --base-href /app/)

# One hash over every file the web build reads, plus the flags and Flutter.
build_inputs_hash() {
    {
        printf '%s\n' "${BUILD_FLAGS[*]}"
        cat .fvmrc
        find lib tool/e2e web assets pubspec.yaml pubspec.lock l10n.yaml -type f \
            -not -path 'lib/l10n/gen/*' -print0 | sort -z | xargs -0 sha256sum
    } | sha256sum | cut -d' ' -f1
}

cmd_build() {
    cd "$ROOT/app"
    [[ -f lib/config/firebase_local.dart ]] ||
        fvm dart run tool/write_firebase_config.dart --placeholder
    local want stamp="$WEB/.inputs.sha256"
    want="$(build_inputs_hash)"
    if [[ -f "$WEB/index.html" && "$(cat "$stamp" 2>/dev/null)" == "$want" ]]; then
        echo "e2e web build is current"
        return 0
    fi
    CAP_CPU_PCT=20 CAP_MEM=4G "$HOME/.claude/scripts/capped.sh" fvm flutter build web \
        "${BUILD_FLAGS[@]}"
    printf '%s\n' "$want" > "$stamp"
}

cmd_down() {
    stop_units "$HOLD_UNIT" "$SERVER_UNIT" "$DB_UNIT" "$MODEL_UNIT" "$GUARD_UNIT"
    if [[ -f "$STATE" ]]; then
        local sandbox
        sandbox="$(sed -n 's/^SANDBOX=//p' "$STATE")"
        [[ "$sandbox" == */tutor-e2e.* && -d "$sandbox" ]] && {
            cp "$sandbox/server.log" "$(dirname "$STATE")/last-server.log" 2>/dev/null || true
            rm -rf "$sandbox"
        }
        rm -f "$STATE"
    fi
    rm -f "$(dirname "$STATE")"/f[0-9]*.json  # a phased flow's send state
    echo "e2e sandbox down"
}

cmd_up() {
    [[ -f "$WEB/index.html" ]] || die "no e2e web build: run $0 build"
    cmd_down >/dev/null
    local sandbox db_port port dev db as_of="" clock="" struggle=0 carry="" nocard="" model="" gate=0
    local learn="" unarchive="" unit_gate="" guard="" rework=""
    local -a pass=() c3=(missing)
    while (($#)); do
        case "$1" in
            --struggle) struggle=1 ;;
            --gate) gate=1 ;;
            --carry) carry="${2:?--carry N}"; shift ;;
            --nocard) nocard="${2:?--nocard due|review}"; shift ;;
            --model-down) model="${2:?--model-down network|refuse}"; shift ;;
            --learn) learn="${2:?--learn S/M}"; shift ;;
            --unit-gate) unit_gate="${2:?--unit-gate fresh|taught}"; shift ;;
            --unarchive) unarchive="${2:?--unarchive S}"; shift ;;
            --rework) rework="${2:?--rework S/M/SLUG}"; shift ;;
            --guard-theory) guard="${2:?--guard-theory JSON}"; shift ;;
            --phase) read -ra c3 <<< "${2:?--phase MODE [S/M ...]}"; shift ;;
            --as-of) as_of="${2:?--as-of T}"; pass+=("$1" "$2"); shift ;;
            *) pass+=("$1") ;;
        esac
        shift
    done
    # The worker lives at --as-of (libfaketime): a past one is also rewound,
    # so its "today" (stats, live card, carry day) matches the copy.
    if [[ -n "$as_of" ]]; then
        clock="$(date -d "$as_of" '+%Y-%m-%d %H:%M:%S')"
        command -v faketime >/dev/null || die "no faketime: sudo pacman -S libfaketime"
    fi
    sandbox="$(mktemp -d "${TMPDIR:-/tmp}/tutor-e2e.XXXXXX")"
    head -c 32 /dev/urandom | base64 > "$sandbox/test.key"
    dev="$("$PY" "$ROOT/scripts/e2e_prepare.py" "$SRC_DATA" "$sandbox/data" "${pass[@]}")"
    ((struggle)) && "$PY" "$ROOT/scripts/e2e_seed.py" struggle "$sandbox/data" --subject "$SUBJECT"
    ((gate)) && "$PY" "$ROOT/scripts/e2e_gate.py" seed "$sandbox/data" --subject "$SUBJECT"
    if [[ -n "$nocard" ]]; then  # F12: no card left to teach
        "$PY" "$ROOT/scripts/e2e_seed.py" nocard "$sandbox/data" --subject "$SUBJECT" --next "$nocard"
    fi
    if [[ -n "$learn" ]]; then  # C4: one untaught card left in module M
        TUTOR_KEY="$sandbox/test.key" "$PY" "$ROOT/scripts/e2e_phase.py" seed "$sandbox/data" \
            --subject "${learn%%/*}" --module "${learn#*/}"
    fi
    [[ -z "$unit_gate" ]] || "$PY" "$ROOT/scripts/e2e_unit_gate.py" seed "$sandbox/data" "$unit_gate"
    [[ -z "$unarchive" ]] || "$PY" -m tutor subject unarchive "$unarchive" --data "$sandbox/data"
    [[ -z "$rework" ]] || TUTOR_KEY="$sandbox/test.key" "$PY" "$ROOT/scripts/e2e_rework_seed.py" "$sandbox" "$rework"
    write_phase "$sandbox" "${c3[@]}"
    if [[ -n "$carry" ]]; then  # the day before the worker's today
        "$PY" "$ROOT/scripts/e2e_seed.py" carry "$sandbox/data" --key "$sandbox/test.key" \
            --minutes "$carry" --day "$(date -d "$(date -d "${clock:-now}" +%F) -1 day" +%F)"
    fi
    mkdir -p "$(dirname "$STATE")" "$sandbox/cache"
    db_port="$(free_port)"
    port="$(free_port)"
    db="http://127.0.0.1:$db_port"
    printf 'SANDBOX=%s\nDB=%s\nPORT=%s\nDEV=%s\nCLOCK=%s\nMODEL=%s\nGUARD=%s\n' \
        "$sandbox" "$db" "$port" "$dev" "$clock" "$model" "$guard" > "$STATE"
    systemd-run --user --quiet --collect --unit="$DB_UNIT" -p RuntimeMaxSec=3600 \
        java -jar "$(emulator_jar)" --host 127.0.0.1 --port "$db_port"
    wait_http "$db/.json" 40 || die "emulator did not start"
    start_server
    grep 'e2e seed' "$sandbox/server.log" || true
    echo "e2e sandbox up: app http://127.0.0.1:$port/app/?db=$db worker $dev${clock:+ clock $clock}"
}

# A second worker start on the same sandbox (F6 again): stats is deleted
# first, so the new worker's publish is visible.
cmd_restart() {
    [[ -f "$STATE" ]] || die "no sandbox: run $0 up"
    if [[ "${1:-}" == --model-down ]]; then
        sed -i "s/^MODEL=.*/MODEL=${2:?--model-down network|refuse|none}/" "$STATE"
    fi
    stop_units "$HOLD_UNIT" "$SERVER_UNIT"
    curl -sf -X DELETE "$(sed -n 's/^DB=//p' "$STATE")/tutor/v1-e2e/stats.json" >/dev/null
    start_server
    echo "e2e sandbox server restarted"
}

# F16: no worker claims anything. The server stops and a static host serves
# the same web build on its port, so a flow can play the worker by writing
# claim/result nodes into the emulator. `restart` brings the worker back.
cmd_hold() {
    [[ -f "$STATE" ]] || die "no sandbox: run $0 up"
    local port root
    port="$(sed -n 's/^PORT=//p' "$STATE")"
    root="$(dirname "$STATE")/hold"
    systemctl --user stop "$SERVER_UNIT" 2>/dev/null || true
    mkdir -p "$root"
    ln -sfn "$WEB" "$root/app"
    systemd-run --user --quiet --collect --unit="$HOLD_UNIT" -p RuntimeMaxSec=3600 \
        "$PY" -m http.server "$port" --bind 127.0.0.1 --directory "$root"
    wait_http "http://127.0.0.1:$port/app/" 40 || die "static host did not start"
    echo "e2e sandbox held: no worker, app on :$port"
}

cmd_flow() {
    local flow="${1:?flow F1..F16}" phase="${2:-all}" db port sandbox
    [[ -f "$STATE" ]] || die "no sandbox: run $0 up"
    db="$(sed -n 's/^DB=//p' "$STATE")"
    port="$(sed -n 's/^PORT=//p' "$STATE")"
    sandbox="$(sed -n 's/^SANDBOX=//p' "$STATE")"
    "$PY" "$ROOT/scripts/e2e_drive.py" "$flow" "$phase" --app "http://127.0.0.1:$port/app/" \
        --db "$db" --card "$CARD" --display "$DISPLAY_ID" \
        --data "$sandbox/data" --focus "$sandbox/focus" --session "$SESSION" --subject "$SUBJECT" \
        --state "$(dirname "$STATE")/${flow,,}.json" --out "$SCREENS/e2e_${flow,,}"
}

main() {
    local cmd="${1:-}"
    shift || true
    case "$cmd" in
        build) cmd_build ;;
        up) cmd_up "$@" ;;
        restart) cmd_restart "$@" ;;
        hold) cmd_hold ;;
        phase) [[ -f "$STATE" ]] || die "no sandbox: run $0 up"
            write_phase "$(sed -n 's/^SANDBOX=//p' "$STATE")" "$@" ;;
        flow) cmd_flow "$@" ;;
        down) cmd_down ;;
        *) die "usage: $0 build | up [--as-of T] [--struggle] [--gate] [--carry N] [--nocard due|review] [--model-down network|refuse] [--unit-gate fresh|taught] [--guard-theory JSON] | restart [--model-down M] | hold | phase MODE [S/M ...] | flow F1|F3..F26|F28|F29 [PHASE] | down" ;;
    esac
}

main "$@"
