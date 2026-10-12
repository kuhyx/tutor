# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``python -m tutor [--port N]``: serve the tutor on localhost.

``python -m tutor migrate [--data DIR]``: the one-off curriculum migration.
"""

from __future__ import annotations

import argparse
import socket
import sys

import uvicorn

from tutor.curriculum import migrate
from tutor.engine import Engine
from tutor.server import create_app

DEFAULT_PORT = 8778


def _port_busy(port: int) -> bool:
    with socket.socket() as probe:
        return probe.connect_ex(("127.0.0.1", port)) == 0


def main(argv: list[str] | None = None) -> int:
    """Serve until interrupted; refuse loudly if the port is taken."""
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["migrate"]:
        return migrate.main(argv[1:])
    parser = argparse.ArgumentParser(prog="python -m tutor", description=__doc__)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--simulate-time",
        action="store_true",
        help="let /api/message skip the engagement clock ahead (scripted runs only)",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="do not resume today's latest session after a restart",
    )
    args = parser.parse_args(argv)
    if _port_busy(args.port):
        print(
            f"port {args.port} is already in use; pick another with --port",
            file=sys.stderr,
        )
        return 1
    engine = Engine(simulated_time=args.simulate_time)
    for card, sid in engine.repair_done_cards():
        print(f"marked {card} done from {sid}", file=sys.stderr)
    engine.backfill_today()
    if not args.fresh and engine.resume_latest():
        print(f"resumed session {engine.session_id}", file=sys.stderr)
    app = create_app(engine)
    print(f"tutor: http://127.0.0.1:{args.port}/", file=sys.stderr)
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
