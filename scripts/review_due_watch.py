#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
r"""Log how fast another device's review lands here (``tutor.review_due_watch``).

Start it as a unit that stops itself after 30 min; it only reads the data dir:

    systemd-run --user --collect --unit=tutor-review-watch -p RuntimeMaxSec=1800 \\
        ~/src/tutor/.venv/bin/python ~/src/tutor/scripts/review_due_watch.py

Rows: ``~/.local/state/tutor/review_due_watch.jsonl``.
"""

from __future__ import annotations

from tutor.review_due_watch import main

if __name__ == "__main__":
    raise SystemExit(main())
