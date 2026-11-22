# tutor -- notes for agents

Read README.md first. These are the invariants that are easy to break.

## Invariants

- **The live server runs from a frozen release**, never the working tree.
  Put a change live only with `scripts/tutor_deploy.sh`; it refuses to swap
  while a reply is in flight. The live server is `tutor.service`; never
  stop or restart it by hand mid-session, and never start a second server
  on :8778 (same relay device id: it would steal the live worker's claims).
- **The HTTP server only answers its own page.** `tutor/local_guard.py`
  refuses (403) any Host that is not a loopback origin of the bound port and
  requires `application/json` (415) plus a same-origin `Origin`, if sent, on
  every POST/PUT/PATCH/DELETE: a cross-site `text/plain` POST or a DNS-rebound
  name must never reach `/api/start` (it runs Claude). Pass `port=` to
  `create_app`; scripted clients must send `Content-Type: application/json`.
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

- `tutor/` -- the server (Starlette: `/` -> `/app/`, the scripted-run API, `/media/`), engine, session, credit.
- `tutor/cards.py`, `tutor/sources.py` -- the card format and the excerpt check.
- `subjects/automation/deck/<topic>.json` -- the PLC / OT security cards;
  `subjects/automation/profile.json` -- the PLC wording of the tutor's rules.
- `tutor/curriculum/` -- generic subjects: plans, just-in-time cards, the
  event-log fold + FSRS, unlock rules, `migrate`; contract in
  `DOCS-contract-curriculum.md`, golden vectors in `contract/`.
- `tests/` -- cards/sources tests; `tutor/tests/` -- everything else. Tests
  read the frozen deck `tests/fixtures/deck` (`TUTOR_DECK_DIR`, set by the
  root `conftest.py`), never the repo deck: `redraft deck` rewrites that one.
- `scripts/tutor_deploy.sh`, `tutor_launch.sh`, `tutor_scripted_run.sh`.

## Commands

- install: `./install.sh` (installs + enables `tutor.service`, the live server; never restarts a running one; also writes the `~/.local/bin/tutor` launcher, `--launcher-only` just that)
- run: `./run.sh` (opens the desktop app at 127.0.0.1:8778/app/, starts `tutor.service` if down; `--no-open` skips the browser)
- deploy: `scripts/deploy.sh` (app web build, then `scripts/tutor_deploy.sh`, which refuses a missing or stale web build; smoke test, wait for idle, `systemctl --user restart tutor.service`)
- test: `.venv/bin/python -m pytest -q` (serial, the CI authority; `-n 6` runs it in parallel with pytest-xdist; tests that count host processes carry `@pytest.mark.exclusive_host` and run alone via the flock in `conftest.py`; a `-k` subset skips the whole-suite coverage gate, and a run from any other python, e.g. a board's `python3 -m pytest`, re-runs itself under `.venv`)
- commit flow (the pytest hook must end < 60 s at any load): `git add` first, then `.venv/bin/python scripts/pytest_stamp.py run` and repeat until it prints `stamp written` (each call < 60 s: chunks of the changed-files selection, progress saved in the git dir, 100% branch coverage on the changed files or on everything for the full suite, stamp keyed by `git write-tree`), then `git commit`. The hook passes in < 1 s on a valid stamp, runs inline when under a quarter of the test files reach the change, and otherwise fails in < 2 s printing that command. Any later `git add` invalidates the stamp; unstaged .py/pyproject changes make the runner refuse; `pre-commit run --all-files` needs a full stamp for the tree: `scripts/pytest_stamp.py run --full` (same loop, nothing staged needed)
- test-changed: `scripts/test_changed.sh`
- redraft (every module's cards drafted again by Fable; README "Redraft"): `.venv/bin/python -m tutor redraft start` (backs up `subjects/`, queues one unit per module; the live server drains the queue and waits while a reply is in flight), `status` (75 = pending, 1 = a unit failed), `report` (prints the report path); a dry run on a copy: `start --data DIR`, then `drain --data DIR` as a `systemd-run --user` unit (it refuses the live data dir)
- code_runner (bubblewrap example runner, was kuhyx/utils): in-repo at `packages/code_runner`, editable via `scripts/setup_dev.sh`; its tests run in the same suite and coverage gate; system python: `packages/code_runner/install.sh`
- lint: `.venv/bin/ruff check . && .venv/bin/python -m mypy tutor tests packages/code_runner/code_runner`
- coverage: `.venv/bin/python -m pytest -q --cov-report=lcov:coverage.lcov`
- coverage-gaps: `coverage-gaps coverage.lcov`
- app deps: `cd app && fvm flutter pub get && dart run tool/write_firebase_config.dart`
- app analyze: `cd app && fvm flutter analyze`
- app test + coverage (full suite): `app/tool/test_chunks.sh`, repeat until it prints `All tests passed` (75 = call again; 6 file chunks of ~25 s, resumable, lcov merged, then `tool/check_coverage.dart`). Never `--total-shards`: it splits tests, every shard still compiles all files. One file: `cd app && fvm flutter test test/<path>_test.dart`
- app build (desktop, served at /app/): `cd app && fvm flutter build web --release --base-href /app/`
- agent E2E (real app + engine + relay on a data-dir copy and a local RTDB emulator over plain HTTP/1.1, as production; README "Agent E2E"): `scripts/e2e_sandbox.sh build`, then `up [--as-of "YYYY-MM-DD HH:MM"]`, `flow F1|F3|F4 send`, then `wait` (75 = pending: again), `check`; F5: `up --struggle --as-of "2026-10-20 17:24:30"`, `flow F5 send|wait|check`; F6: `up --as-of "2026-10-24 20:00" --carry 130`, `flow F6`, `restart`, `flow F6 again`; F7 (desktop Focus screen, sandboxed `FOCUS_PROJECT_DATA`): `up`, `flow F7`; F9/F10 (check-in card): a fresh `up` each, `flow F9`, `flow F10`;  F15 (interview milestone row): a fresh `up`, `flow F15` (`send` only creates the project, `check` only asserts); F11 (unbacked line, needs focus_project >= 0.10.0 in `E2E_FOCUS_SRC`): a fresh `up`, `flow F11`; F12 (result kind of a forced no_card_left): `up --nocard due|review`, `flow F12`; F13 (outage codes + glyphs, no model turn): a fresh `up`, `flow F13 rate_limit|overloaded|network` (one call each), then Read the three frames; F14 (real failures, one phase per call): `up`, `flow F14 drill`, `flow F14 coach`, then `restart --model-down network|refuse` and `flow F14 subject`, `flow F14 module`, `restart --model-down <other>`, `flow F14 module-retry`; F16 (every code, no-card, pause and phase glyph; the flow plays the worker): `up`, `hold`, then `flow F16 codes|codes2|nocard|phases|pauses` (one call each) and Read the frames; F17 (a keyless desktop page recovers the e2e passphrase from the server, then the lock is the fallback): a fresh `up`, `flow F17`;  F18 (a split moves the session to the next card; resumes the live session, needs `up` without `--as-of`, a faked clock breaks the model): `flow F18 send|wait|check`; F19 (archive a subject on Home, then undo): a fresh `up`, `flow F19`; F20 (a planted interrogation path shapes the tutor's first turn and is shown nowhere; needs `up` without `--as-of` and `E2E_SUBJECT=<a subject with an untaught card, e.g. product-and-design-taste>` on every call): a fresh `up`, `flow F20 send|wait|check`; F21 (Next opens the module gate's review, passing it starts the next module; then the bubble's flag, the in-box hint bulb and Send; needs `up` without `--as-of` and a subject with an unstarted module after a taught one, e.g. `E2E_SUBJECT=product-and-design-taste` on every call): a fresh `up --gate`, `flow F21 send|wait|check`, then `flow F21 again` (75 = the hint's reply is pending: again); units are per worktree; `down` (one call each, < 60 s)
- app screenshots: `cd app && fvm flutter build web --release -t tool/fixture/main.dart -o build/web_fixture --base-href /app/`, serve with `TUTOR_WEBAPP_DIR=$PWD/build/web_fixture .venv/bin/python -m uvicorn --factory tutor.webapp:standalone_app --port 8791`, then `tool/screenshot.sh /session 1366x768 build/screens/x.png` (needs an Xvfb on :97)
