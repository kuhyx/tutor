# Tutor (Flutter client)

The phone (Android) and desktop (web build in a Chrome `--app` window) client
for the tutor. It talks only to the Firebase RTDB relay described in
`../DOCS-contract.md` and `../DOCS-contract-curriculum.md`; the PC Python
worker answers. Card review works offline.

## Firebase identifiers (never committed)

This repo is public, so the sync uid, API key, database URL and Google Web
OAuth client id are not in source (DOCS-contract §10). They live in the
gitignored `lib/config/firebase_local.dart`, written once per checkout:

```bash
cd app
dart run tool/write_firebase_config.dart            # from ~/.config/crdt-sync/firebase.json
dart run tool/write_firebase_config.dart --placeholder   # CI: empty values
```

The client id comes from `$TUTOR_GOOGLE_SERVER_CLIENT_ID`, else
`webClientId` in `firebase.json`, else todo's committed `kServerClientId`.
Without the file the app does not compile: that is deliberate. A
`--dart-define` that a bare `flutter build apk` leaves empty would ship a
sign-in button that can never work. A placeholder build compiles and shows
"not configured" instead of a sign-in button.

## Commands (from `app/`, SDK pinned in `.fvmrc`)

- deps: `fvm flutter pub get`
- analyze: `fvm flutter analyze`
- test: `fvm flutter test` (one file: `fvm flutter test test/<path>_test.dart`)
- coverage: `fvm flutter test --coverage` (writes `coverage/lcov.info`)
- build (desktop web, served by the tutor server at `/app/`):
  `fvm flutter build web --release --base-href /app/`
- build (Android): `fvm flutter build apk --release` (takes minutes)

## Layout

- `lib/config/` build-time Firebase identifiers.
- `lib/sync/` Google sign-in, REST RTDB client (ETag writes), SSE streaming.
- `lib/model/` typed, immutable contract records (§3/§4/§6, curriculum §1-§4).
- `lib/relay/` request relay (§4); `lib/presence/` PC presence (§5).
- `lib/log/` offline event log and the FSRS fold (curriculum §4/§5).
- `lib/storage/` per-install key-value store and device id.
- `lib/home/` Home data (catalog cache by `rev.catalog`, due count).
- `lib/session/` the live session feed, answer boxes, the tiny markdown.
- `lib/plan/`, `lib/history/`, `lib/progress/`, `lib/review/`,
  `lib/editor/`, `lib/feedback/`: each screen's logic.
- `lib/app/` service wiring; `lib/ui/` the screens (`ui/nav.dart` routes).
- `tool/fixture/` an in-memory build for screenshots; `tool/screenshot.sh`.

## Desktop

The desktop app is this web build in a Chrome `--app` window: `../run.sh`
opens `http://127.0.0.1:8778/app/` with a fixed profile
(`~/.local/share/tutor-desktop/profile`) once the running server serves it
(`tutor/webapp.py`, build dir `$TUTOR_WEBAPP_DIR`, default `app/build/web`).
The app scales itself by the display it is on (`lib/util/ui_scale.dart`:
x2 on a 4K monitor at DPR 1, x1 up to full HD), so layouts work in full-HD
units everywhere; wide windows get two columns. It signs in without Google: on first start the page fetches the PC's seeded
session from `/app/sync-credentials` (served once per server process,
same-origin localhost only, uid checked) and keeps it in its own store.

## Screenshots (never on the real display)

```bash
fvm flutter build web --release -t tool/fixture/main.dart -o build/web_fixture --base-href /app/
systemd-run --user --unit=tutor-webshot -E TUTOR_WEBAPP_DIR=$PWD/build/web_fixture \
  -p WorkingDirectory=$PWD/.. ../.venv/bin/python -m uvicorn --factory \
  tutor.webapp:standalone_app --port 8791
systemd-run --user --unit=tutor-xvfb /usr/bin/Xvfb :97 -screen 0 1400x1000x24
tool/screenshot.sh /session 1366x768 build/screens/session.png
```

Routes: `-` (Home), `/plan/<subject>`, `/session`, `/history[/<sid>]`,
`/progress`, `/editor[/<subject>]`, `/review`, `/report`.

## Coverage

Logic files (everything in `lib/` except `lib/ui/` and `main.dart`) are held
to 100%: `fvm flutter test --coverage && dart run tool/check_coverage.dart`.
The checker honours `// coverage:ignore-*` markers, which `flutter test`
itself ignores; only platform-channel code carries them.

## FSRS

`lib/log/fsrs6.dart` is a port of py-fsrs 6.3.2's Scheduler, not the Dart
`fsrs` package: fsrs 2.0.1 has older default weights and clamps the Easy
initial difficulty in mean reversion, so it diverged from Python on the first
review. `test/log/fsrs_vectors_test.dart` loads `../contract/fsrs_vectors.json`
(the Python side writes it) and skips while the file does not exist.
