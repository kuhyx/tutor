#!/bin/bash
# ============================================================================
# tutor_model_sandbox.sh -- run the tutor model's claude CLI inside bubblewrap.
#
# The tutor conversation has every Claude Code tool (Bash, web, files,
# subagents) with permissions bypassed, so the process is fenced in here
# instead: tutor.research sets this script as the SDK's cli_path. Inside:
#   - /usr and a short allowlist of /etc, read-only (DNS, TLS, users, locale);
#   - a scratch HOME ($TUTOR_MODEL_SANDBOX/home, same path inside and out)
#     the model may install into, and a fresh working dir per process;
#   - the real CLI binary alone, read-only, at /opt/claude/claude;
#   - full network, a private /tmp, /proc of its own pid namespace.
# Nothing else of $HOME: no data dir, ledger, releases, repo or ~/.claude.
# The CLI's login is a copy tutor.research writes into the scratch HOME
# (access token only). The environment is cleared down to an allowlist, so
# TUTOR_* and agent sockets stay out.
#
# Usage (env from tutor.research):
#   TUTOR_MODEL_SANDBOX=<dir> TUTOR_MODEL_CLI=<claude binary> \
#       tutor_model_sandbox.sh [cli args...]
# ============================================================================

set -euo pipefail

: "${TUTOR_MODEL_SANDBOX:?TUTOR_MODEL_SANDBOX (the scratch root) is required}"
: "${TUTOR_MODEL_CLI:?TUTOR_MODEL_CLI (the real claude binary) is required}"
readonly BOX_HOME="${TUTOR_MODEL_SANDBOX}/home"
readonly WORK_ROOT="${BOX_HOME}/work"
readonly CLI_INSIDE=/opt/claude/claude
# Read-only /etc entries the CLI, git, pip, npm and curl need. Never all of
# /etc: it holds world-readable secrets (the ledger key in workout-locker/).
readonly ETC_ALLOW=(
    resolv.conf hosts host.conf nsswitch.conf gai.conf passwd group
    localtime locale.conf os-release ld.so.cache ld.so.conf ld.so.conf.d
    ssl ca-certificates protocols services mime.types inputrc profile
    bash.bashrc gitconfig wgetrc
)

die() {
    echo "tutor_model_sandbox: $*" >&2
    exit 1
}

# bwrap args for the root symlinks (/bin -> usr/bin on Arch) or dirs.
root_links() {
    local name
    for name in bin sbin lib lib64; do
        if [[ -L "/${name}" ]]; then
            args+=(--symlink "$(readlink "/${name}")" "/${name}")
        elif [[ -d "/${name}" ]]; then
            args+=(--ro-bind "/${name}" "/${name}")
        fi
    done
}

# --setenv for each allowed variable of the caller's environment.
pass_env() {
    local name
    while IFS= read -r name; do
        case "$name" in
            CLAUDE_CONFIG_DIR) ;;
            CLAUDE_* | ANTHROPIC_* | DISABLE_* | BASH_DEFAULT_TIMEOUT_MS | \
                BASH_MAX_TIMEOUT_MS | MAX_THINKING_TOKENS | LANG | LC_* | TZ | \
                NO_COLOR | USER | LOGNAME)
                args+=(--setenv "$name" "${!name}")
                ;;
        esac
    done < <(compgen -e)
}

main() {
    [[ -x "$TUTOR_MODEL_CLI" ]] || die "not executable: $TUTOR_MODEL_CLI"
    command -v bwrap >/dev/null || die "bwrap (bubblewrap) is not installed"
    mkdir -p "$WORK_ROOT"
    # Per-process working dirs older than a day are left-overs: drop them.
    find "$WORK_ROOT" -mindepth 1 -maxdepth 1 -mmin +1440 -exec rm -rf {} + || true
    local work
    work="$(mktemp -d "${WORK_ROOT}/XXXXXXXX")"

    local -a args=(
        --unshare-all --share-net --die-with-parent --new-session
        --clearenv
        --ro-bind /usr /usr
        --proc /proc --dev /dev --tmpfs /tmp --tmpfs /var/tmp --tmpfs /run
        --ro-bind "$TUTOR_MODEL_CLI" "$CLI_INSIDE"
        --bind "$BOX_HOME" "$BOX_HOME"
        --chdir "$work"
    )
    root_links
    local entry
    for entry in "${ETC_ALLOW[@]}"; do
        args+=(--ro-bind-try "/etc/${entry}" "/etc/${entry}")
    done
    pass_env
    args+=(
        --setenv HOME "$BOX_HOME"
        --setenv PWD "$work"
        --setenv TMPDIR /tmp
        --setenv PATH "${BOX_HOME}/.local/bin:${BOX_HOME}/.npm-global/bin:/usr/local/bin:/usr/bin"
        --setenv NPM_CONFIG_PREFIX "${BOX_HOME}/.npm-global"
        --setenv PIP_BREAK_SYSTEM_PACKAGES 1
    )
    exec bwrap "${args[@]}" -- "$CLI_INSIDE" "$@"
}

main "$@"
