#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Drive a new subject on a SCRATCH data dir with the real model, no relay.

One step per run (each is minutes of model time; run it detached and poll):
  curriculum_smoke.py --data DIR new "I want to understand how X works"
  curriculum_smoke.py --data DIR approve SUBJECT
  curriculum_smoke.py --data DIR generate        # every pending module
  curriculum_smoke.py --data DIR show SUBJECT    # modules and live cards
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from tutor.curriculum import handlers


def main() -> int:
    """Run one step."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("step", choices=("new", "approve", "generate", "show"))
    parser.add_argument("arg", nargs="?", default="")
    args = parser.parse_args()
    if args.data.resolve() == (Path.home() / ".local/share/tutor").resolve():
        sys.exit("refusing to run on the live data dir")
    ctx = handlers.Context(args.data)
    out: object
    if args.step == "new":
        out = handlers.BUILD_HANDLERS["subject_new"]({"text": args.arg}, ctx)
    elif args.step == "approve":
        plan = ctx.subjects.plan(args.arg)
        rev = plan.rev if plan else 0
        body = {"subject": args.arg, "plan_rev": rev}
        out = [handlers.BUILD_HANDLERS["plan_approve"](body, ctx)]
        out.append(handlers.fold_and_advance(ctx))
    elif args.step == "generate":
        out = [handlers.generate(ctx, s, m) for s, m in handlers.pending(ctx)]
    else:
        plan = ctx.subjects.plan(args.arg)
        cards = ctx.subjects.cards(args.arg)
        out = {
            "modules": [(m.id, m.status, m.cards, m.error) for m in plan.modules]
            if plan
            else [],
            "cards": [
                [cid, c.module, c.front, c.source]
                for cid, c in cards.items()
                if not c.suspended
            ],
        }
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
