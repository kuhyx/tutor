# Install the Tutor app on the phone for the first time

REMOVE ME AFTER FINISH

## what
First install of `com.kuhy.tutor` (release-signed with the shared key) on the
Pixel 6a `23181JEGR08034`, signed in with the sync Google account, then the
Q19 check. Prepared 2026-10-12 without touching the phone: release signing in
`app/android/app/build.gradle.kts`, `app/android/key.properties` (gitignored
copy of `~/.android/release/key.properties`), focus whitelist source
(phone-focus-mode `cee67fe`), `.github/workflows/release-apk.yml`,
`scripts/register_oauth_client.sh`, `scripts/set_release_secrets.sh`.

Status 2026-10-12: steps 3-6 done (focus-owner versionCode 214 with the
tutor whitelist; tutor 81 installed, `hidden=false`, sign-in screen shows).
Left: step 2 (OAuth client), step 7, Q19.

## done
- `adb -s 23181JEGR08034 shell dumpsys package com.kuhy.tutor | grep -oE 'hidden=[a-z]+'` prints `hidden=false`
- `scripts/register_oauth_client.sh --verify-only` exits 0
- every Q19 box below ticked

## steps (in order)

1. **Prereqs (seconds).** All three must pass:
   ```bash
   cd ~/src/tutor
   git check-ignore -q app/android/key.properties && echo key-ignored
   scripts/register_oauth_client.sh --sha1      # 58:09:D4:CB:...:97:44
   ! grep -q "''" app/lib/config/firebase_local.dart && echo firebase-set
   ```
   `firebase_local.dart` missing/empty: `cd app && dart run tool/write_firebase_config.dart`.

2. **Android OAuth client** (Google has no API; the script opens the console,
   puts Name / Package / SHA-1 on the clipboard in form order):
   ```bash
   scripts/register_oauth_client.sh
   ```
   At its last prompt ("Install the APK, sign in...") press Ctrl-C; step 7
   runs the verification.

3. **Focus whitelist on the phone, BEFORE installing.** The Pixel's policy is
   bundled in the focus-owner APK (Device Owner; `pm unhide` is denied), so the
   source change needs a focus-owner rebuild + reinstall, split the same way
   (one line per action, each via capped.sh as in step 4), then
   `adb -s 23181JEGR08034 install -r build/app/outputs/flutter-apk/app-release.apk`:
   ```bash
   cd ~/src/phone-focus-mode/focus-owner
   scripts/build_apk.sh prep --phone 23181JEGR08034   # then dart, jvm, r8, apk
   ```
   Enforcement runs on the 15-min alarm, not on install
   (`adb shell dumpsys alarm | grep -A4 EnforcementAlarmReceiver`). The
   installed policy already allows the `com.kuhy` prefix, so tutor is
   probably not hidden even before this; step 6 checks.
   (Rooted BL9000 only: push `config.sh` + `focus_ctl.sh restart`, see memory
   `project-new-android-app-needs-focus-whitelist`.)

4. **Build the release APK** -- five steps, each < 30 s under the 60 s cap
   (`scripts/build_apk.sh`; arm64 only, lintVital skipped, R8 kept):
   ```bash
   cd ~/src/tutor    # one line per action; prefix each with
                     # CAP_MEM=4G CAP_CPU_PCT=20 ~/.claude/scripts/capped.sh
   scripts/build_apk.sh prep --phone 23181JEGR08034
   scripts/build_apk.sh dart
   scripts/build_apk.sh jvm
   scripts/build_apk.sh r8
   scripts/build_apk.sh apk
   ```
   versionCode = commit count (CI's scheme), raised to installed+1 by
   `--phone` through phone_deploy's ceiling rule. The `apk` step already
   fails unless the signer is the kuhy key; to re-check by hand:
   ```bash
   "$(find ~/sdk/Android/Sdk/build-tools -name apksigner -type f | sort -V | tail -1)" \
     verify --print-certs app/build/app/outputs/flutter-apk/app-release.apk | grep -E 'DN|SHA-256'
   ```
   SHA-256 must be `9dcc2e6c...b98f846`.

5. **Install (phone-deploy skill rules: `install -r`, NEVER uninstall /
   `pm clear`):**
   ```bash
   adb devices                       # 23181JEGR08034 must be listed
   adb -s 23181JEGR08034 install -r app/build/app/outputs/flutter-apk/app-release.apk
   ```

6. **Not hidden by focus-owner:**
   `adb -s 23181JEGR08034 shell dumpsys package com.kuhy.tutor | grep -oE 'hidden=[a-z]+'`
   -> `hidden=false`. `hidden=true` means step 3's alarm has not fired yet.

7. **Sign in, then verify:** open Tutor on the phone, "Sign in with Google",
   pick the sync account. Then `scripts/register_oauth_client.sh --verify-only`
   (exit 0 = Home screen showing). "account reauth failed" / UNREGISTERED =
   the OAuth client has not propagated yet (minutes) or the SHA-1 differs.

8. **Optional, for tag-built APKs later:** `scripts/set_release_secrets.sh`
   (sets the 5 secrets from local files; `--dry-run` shows names + lengths),
   then `git tag v1.0.0 && git push origin v1.0.0` (one tag; never `--tags`).

## verify: Q19 (from handoff 20261012-tutor-own-repo-flutter-generic.md)
On the Pixel, **wifi OFF, no VPN**:
- [ ] install APK (steps 4-6)
- [ ] sign in (the handoff says "enter password"; Firebase auth is Google
      sign-in only now, step 7)
- [ ] type "I want to learn how a car works"
- [ ] approve the plan
- [ ] finish one taught card
- [ ] see that card in review later
- [ ] credit row in the ledger
- [ ] the same session continues in the desktop Flutter window
- [ ] the PLC subject still works
- [ ] tests green in kuhyx/tutor
- [ ] `grep -ri "automation tutor"` empty outside `subjects/automation`

## read first
- `~/.claude/skills/phone-deploy/SKILL.md` (exit codes 30-37)
- memory `reference-focus-owner-policy-deploy`, `reference-android-release-signing`
- `DOCS-contract.md` §10 (identifiers stay out of this public repo)
