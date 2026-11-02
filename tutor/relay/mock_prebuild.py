# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Build mock papers ahead of time (``python -m tutor mock-prebuild N``).

A pre-built paper uses only saved material: curated MCQs (keys from a real
sandbox run), saved SQL drills and one palindrome task, so no model call is
needed and ``mock start`` later answers at once.
"""

from __future__ import annotations

import argparse
import asyncio
import secrets
import sys
import time

from tutor.relay import mock, mock_mcq, mock_palin, mock_pool, mock_sql, mock_store

PALIN_ORDER = ("subseq", "substr", "subseq")


async def _build_one(index: int) -> str:
    rnd = secrets.SystemRandom()
    codes, drills = mock_pool.used()
    seen = drills | mock_store.seen_drills()
    sql = await mock_sql.pick(rnd, seen, generate=False)
    palin_key = PALIN_ORDER[index % len(PALIN_ORDER)]
    palin = next(t for t in mock_palin.TASKS if t.key == palin_key)
    questions = await asyncio.to_thread(mock_mcq.curated, rnd, codes)
    parts = mock.Parts(questions, sql, palin, [])
    paper = mock.compose(rnd, time.time(), 0, parts)
    mock_pool.stock(paper)
    return str(paper["id"])


def build(count: int) -> list[str]:
    """Build and stock ``count`` papers; returns their ids."""
    start = mock_pool.count()
    return [asyncio.run(_build_one(start + n)) for n in range(count)]


def main(argv: list[str]) -> int:
    """Build the papers and print ``ready <id> <seconds>`` for each."""
    parser = argparse.ArgumentParser(prog="python -m tutor mock-prebuild")
    parser.add_argument("count", type=int, nargs="?", default=3)
    args = parser.parse_args(argv)
    if args.count < 1:
        parser.error("count must be at least 1")
    for _ in range(args.count):
        begun = time.perf_counter()
        (paper_id,) = build(1)
        sys.stdout.write(f"ready {paper_id} {time.perf_counter() - begun:.1f}s\n")
    return 0
