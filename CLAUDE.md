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
- `subjects/automation/deck/<topic>.json` -- the PLC / OT security cards;
  `subjects/automation/profile.json` -- the PLC wording of the tutor's rules.
- `tutor/curriculum/` -- generic subjects: plans, just-in-time cards, the
  event-log fold + FSRS, unlock rules, `migrate`; contract in
  `DOCS-contract-curriculum.md`, golden vectors in `contract/`.
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
- app deps: `cd app && fvm flutter pub get && dart run tool/write_firebase_config.dart`
- app analyze: `cd app && fvm flutter analyze`
- app test: `cd app && fvm flutter test` (one file: `fvm flutter test test/<path>_test.dart`)
- app coverage: `cd app && fvm flutter test --coverage && dart run tool/check_coverage.dart`
- app build (desktop, served at /app/): `cd app && fvm flutter build web --release --base-href /app/`
- app screenshots: `cd app && fvm flutter build web --release -t tool/fixture/main.dart -o build/web_fixture --base-href /app/`, serve with `TUTOR_WEBAPP_DIR=$PWD/build/web_fixture .venv/bin/python -m uvicorn --factory tutor.webapp:standalone_app --port 8791`, then `tool/screenshot.sh /session 1366x768 build/screens/x.png` (needs an Xvfb on :97)
