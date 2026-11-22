#!/bin/bash
# ============================================================================
# scratch_phase.sh OUT KEY -- the guard's C3 row (theory_phase.json), signed
# again with a scratch KEY into OUT, for tutor_deploy.sh's smoke server.
#
# The smoke server signs with a random key, so the real row fails its HMAC:
# nothing is teachable and a live LeetCode session would not resume. No real
# row: no OUT either (the same as the live server sees). Needs jq.
# ============================================================================
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
readonly REPO
readonly PHASE="${TUTOR_THEORY_PHASE:-$HOME/.local/share/leetcode_guard/theory_phase.json}"

main() {
    local out="${1:?OUT}" key="${2:?KEY}"
    local -a grant
    [[ -f "$PHASE" ]] || return 0
    mapfile -t grant < <(jq -r 'if .detail.phase == "theory"
        then "theory", (.detail.teachable[] | join("/")) else "solve" end' "$PHASE")
    "$REPO/.venv/bin/python" "$REPO/scripts/e2e_phase.py" write "$out" --key "$key" \
        "${grant[@]}" >/dev/null
}

main "$@"
