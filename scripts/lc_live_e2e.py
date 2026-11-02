#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Drive one problem-coach request through the REAL libraries and model.

Usage: ``lc_live_e2e.py <kind> '<json body>'`` with ``TUTOR_DATA``,
``TUTOR_KEY``, ``TUTOR_SOURCE_CACHE``, ``FOCUS_PROJECT_DATA`` and
``LEETCODE_COACH_SESSIONS_DIR`` pointing into a scratch dir (the wrapper
``lc_live_e2e.sh`` sets them). Anki is pointed at a dead port and the .apkg
goes into the scratch dir, so nothing of kuhy's is touched.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace
from typing import Any, cast

from leetcode_coach import anki_connect, make_cards

from tutor.curriculum.context import Context
from tutor.relay import protocol
from tutor.relay.chat import CHAT_HANDLERS
from tutor.relay.errors import RequestError
from tutor.store import data_dir

RID = "01J00000000000000000000000"
DEV = "00000000-0000-4000-8000-000000000000"
SCRATCH_ENV = "LEETCODE_COACH_SESSIONS_DIR"


def main(kind: str, raw_body: str) -> int:
    """Run ``kind`` once, print its result, return the exit code."""
    scratch = Path(os.environ[SCRATCH_ENV]).parent
    if not str(data_dir()).startswith(str(scratch)):
        print("refusing: TUTOR_DATA is outside the scratch dir")
        return 2
    anki_connect.URL = "http://127.0.0.1:9"
    make_cards.OUT_DIR = scratch / "learn"
    now = time.time()
    req = {
        "kind": kind,
        "dev": DEV,
        "created": int(now * 1000),
        "body": json.loads(raw_body),
    }
    ctx = SimpleNamespace(
        now=time.time,
        request=SimpleNamespace(created_ms=int(now * 1000)),
        body=protocol.validate(RID, req).body,
        engine=SimpleNamespace(ctx=Context(data_dir())),
    )
    started = time.monotonic()
    try:
        out: Any = asyncio.run(CHAT_HANDLERS[kind](cast("Any", ctx)))
    except RequestError as err:
        logging.getLogger(__name__).warning("%s failed: %s", kind, err)
        out = {"error": err.code, "message": str(err)}
    print(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"[{kind}: {time.monotonic() - started:.1f}s]", file=sys.stderr)
    return 1 if "error" in out else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
