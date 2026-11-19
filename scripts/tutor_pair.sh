#!/bin/bash
# Pair a phone with the public tutor page (DOCS-public.md): ask the live server
# for a single-use link (valid 5 minutes), print it with a QR code, and with
# --adb [serial] open it on a USB-connected phone (default: the only device).
#   scripts/tutor_pair.sh            # URL + QR for kuhy's phone camera
#   scripts/tutor_pair.sh --adb      # open it on the phone over adb
# Needs: curl, jq (and qrencode / adb when used).
set -euo pipefail

readonly PORT="${TUTOR_PORT:-8778}"
readonly ORIGIN="http://127.0.0.1:${PORT}"

die() {
	echo "Error: $*" >&2
	exit 1
}

command -v jq >/dev/null || die "jq is required"
url="$(curl -fsS -X POST "${ORIGIN}/api/pair" -H 'Content-Type: application/json' \
	-H "Origin: ${ORIGIN}" -d '{}' | jq -er .url)" || die "tutor.service not answering on ${ORIGIN}"

if [[ "${1:-}" == "--adb" ]]; then
	command -v adb >/dev/null || die "adb is required"
	serial=()
	[[ -n "${2:-}" ]] && serial=(-s "$2")
	adb "${serial[@]}" shell am start -a android.intent.action.VIEW -d "$url" >/dev/null
	echo "opened on the phone"
else
	echo "$url"
	command -v qrencode >/dev/null && qrencode -t ANSIUTF8 "$url"
fi
