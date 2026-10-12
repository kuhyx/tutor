#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Record a real ``regenerate --now`` run as a replayable test fixture.

Runs ``python -m tutor regenerate SUBJECT MODULE --now`` on ``--data``
(a SCRATCH copy, never the live data dir) with the real model and the real
MediaWiki API, recording every API answer (extracts clipped to what the
pipeline reads) and every model reply in call order, into ``--out``.
``tutor/tests/test_relevance_fixture.py`` replays it offline.

Usage: .venv/bin/python scripts/record_cardgen_fixture.py --data DIR \
           --out tutor/tests/data/cardgen/NAME.json SUBJECT MODULE
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any

from tutor import sources
from tutor.curriculum import modelcall, regen, wiki
from tutor.curriculum.context import Context

_CLIP_WORDS = 2600
ATTRIBUTION = (
    "Page texts: English Wikipedia / Wikibooks contributors, CC BY-SA 4.0, "
    "clipped; fetched through the MediaWiki API."
)


class Recorder:
    """Real fetch and model, with every answer kept."""

    def __init__(self) -> None:
        """Start empty."""
        self.fetched: dict[str, Any] = {}
        self.replies: list[dict[str, Any]] = []

    def fetch(self, url: str) -> bytes:
        """The real API answer; recorded with long extracts clipped."""
        body = wiki.http_get(url)
        data = json.loads(body)
        for page in data.get("query", {}).get("pages", []) or []:
            if isinstance(page, dict) and isinstance(page.get("extract"), str):
                page["extract"] = " ".join(page["extract"].split()[:_CLIP_WORDS])
        self.fetched[url] = data
        return json.dumps(data).encode()

    def model(self, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        """The real model's answer, recorded."""
        reply = modelcall.ask_model(system, prompt, schema)
        self.replies.append({"system": system.splitlines()[0], "reply": reply})
        return reply


def main() -> int:
    """Record one run."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("subject")
    parser.add_argument("module")
    args = parser.parse_args()
    if args.data.resolve() == (Path.home() / ".local/share/tutor").resolve():
        sys.exit("refusing to record on the live data dir; use a scratch copy")
    rec = Recorder()
    folder = args.data / "subjects" / args.subject
    before = {
        name: json.loads((folder / f"{name}.json").read_text("utf-8"))
        for name in ("meta", "plan", "cards")
    }
    with tempfile.TemporaryDirectory() as cache:
        os.environ["TUTOR_WIKI_CACHE"] = cache  # every API call reaches fetch
        # The clipped extracts must never reach the real excerpt-check cache.
        vars(sources)["CACHE_DIR"] = Path(cache) / "sources"

        def make(root: Path) -> Context:
            return Context(root, model=rec.model, fetch=rec.fetch)

        code = regen.main(
            [args.subject, args.module, "--data", str(args.data), "--now"], make
        )
    out = {
        "attribution": ATTRIBUTION,
        "subject": args.subject,
        "module": args.module,
        "before": before,
        "fetch": rec.fetched,
        "model": rec.replies,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", "utf-8")
    return code


if __name__ == "__main__":
    sys.exit(main())
