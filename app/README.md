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
- run (web): `fvm flutter run -d chrome`
- build: `fvm flutter build apk --release` (takes minutes)

## Layout

- `lib/config/` build-time Firebase identifiers.
- `lib/sync/` Google sign-in, REST RTDB client (ETag writes), SSE streaming.
- `lib/model/` typed, immutable contract records (§3/§4/§6, curriculum §1-§4).
- `lib/relay/` request relay (§4); `lib/presence/` PC presence (§5).
- `lib/log/` offline event log and the FSRS fold (curriculum §4/§5).
- `lib/storage/` per-install key-value store and device id.
- `lib/ui/` sign-in and Home.

## FSRS golden vectors

`test/log/fsrs_vectors_test.dart` loads `../contract/fsrs_vectors.json` (the
Python side writes it) and skips while the file does not exist.
