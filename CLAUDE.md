# tutor -- notes for agents

Read README.md first. These are the invariants that are easy to break.

## Invariants

- **The live server runs from a frozen release**, never the working tree.
  Put a change live only with `scripts/tutor_deploy.sh`; it refuses to swap
  while a reply is in flight. Never kill the live unit by hand mid-session.
- **Tests never touch real data.** `tutor/tests/conftest.py` moves HOME, the
  data dir, the ledger key and the image cache into `tmp_path` and blocks
  the network. Keep it that way; the real ledger mints gaming time.
- **Every card is checked against its source by code.** `excerpt` is verbatim
  text from `source`. Never hand-edit an excerpt to "make it pass".
- **Ids are stable.** Session transcripts and the done-set key on card ids.
- **Names are `tutor`** (renamed from `automation_tutor` 2026-10-12): env vars
  `TUTOR_*`, data `~/.local/share/tutor`, logs `~/.local/state/tutor`,
  releases `~/.local/lib/tutor-live`, caches `~/.cache/tutor/`. The old
  `~/.local/share/automation_tutor` and `~/.local/state/automation_tutor` are
  read-only backups; never write to them.

## Layout

- `tutor/` -- the server (Starlette), engine, session, credit, static page.
- `tutor/cards.py`, `tutor/sources.py` -- the card format and the excerpt check.
- `subjects/automation/deck/<topic>.json` -- the PLC / OT security cards.
- `tests/` -- cards/sources tests; `tutor/tests/` -- everything else.
- `scripts/tutor_deploy.sh`, `tutor_launch.sh`, `tutor_scripted_run.sh`.

## Commands

- run: `./run.sh` (opens the tutor on 127.0.0.1:8778, starts it from the live release if down; `--no-open` skips the browser)
- deploy: `scripts/tutor_deploy.sh` (smoke test, wait for idle, swap the live server)
- test: `.venv/bin/python -m pytest -q`
- test-changed: `scripts/test_changed.sh`
- lint: `.venv/bin/ruff check . && .venv/bin/python -m mypy tutor tests`
- coverage: `.venv/bin/python -m pytest -q --cov-report=lcov:coverage.lcov`
- coverage-gaps: `coverage-gaps coverage.lcov`
