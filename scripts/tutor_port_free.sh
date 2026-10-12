#!/bin/bash

# ============================================================================
# Exit 0 when nothing listens on 127.0.0.1:<port>, else name the holder and
# exit 1.
#
# tutor.service runs this before every start. The engine resumes and the
# relay starts in the app lifespan, BEFORE uvicorn binds the port, so a second
# server would run as the same relay device for a moment: it takes over the
# live worker's claims as "dead" and deletes its presence beat when it exits
# on the bind error. Refusing to start is the only safe answer.
# ============================================================================

set -euo pipefail

main() {
    local port="${1:?usage: tutor_port_free.sh <port>}" holder
    holder="$(ss -ltnpH "sport = :$port")"
    if [[ -n "$holder" ]]; then
        echo "tutor: :$port is already served ($holder); not starting a second server" >&2
        exit 1
    fi
}

main "$@"
