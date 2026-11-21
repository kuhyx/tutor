# Tutor contract: security and end-to-end encryption

Split out of `DOCS-contract.md` §10 and §12 (the contract wins on any conflict).

## 10. Security
- Public repo: no uid, email, API key or tokens in source/docs; config from
  `~/.config`. Scan history before the first push.
- All RTDB content is untrusted: worker validates kind, id regexes, types,
  sizes; ignores unknown fields; never builds a path/filename from an
  unvalidated id.
- No MCP, settings or hooks for any model; tools only for the tutor, in
  bubblewrap (`research.py`), else `isolated_options`; `wrap_learner`.
- Client: markdown with raw HTML off; https links only; image host allowlist;
  SVG only from worker.
- Credit unforgeable via RTDB: root-owned HMAC key stays on the PC; time
  inputs server-stamped.
- Tokens: Android keystore; `~/.config/tutor/` on PC. Transcripts, reviews
  and everything else in RTDB are end-to-end encrypted (§12).

## 12. End-to-end encryption (2026-11-12)
- Root `tutor/v1-e2e` (`E2eLayout.of("tutor/v1")`). Key = Argon2id of the
  shared crdt-sync password; the clear header (salt, cost, check MAC, never a
  key) is a JSON string leaf at `tutor/e2e`. Worker: `~/.config/crdt-sync/password`;
  app: the OS keystore (crdt_sync_flutter, key cached after the first derive).
- Keys stay clear (ids, slugs, `m0001`): `orderBy="$key"`, PATCH and SSE paths
  are unchanged. Every *unit* is stored as `{"_e2e": blob, <clear>}`; blob =
  crdt_sync `E2eCipher` (XChaCha20-Poly1305) of the unit's JSON, AAD = the
  unit's full path. Units: `live`, `prefs/*`, `stats/*`, `presence/workers/*`
  (`beat` clear), `presence/clients/*` (`seen` clear), `uploads/*/*`,
  `requests/*/req` (`created` clear), `requests/*/result` (`at` clear),
  `sessions/*/meta/*|msgs/*|receipts/*|user/*|progress/steps/*`,
  `session_index/*`, `subjects/*/meta|plan|cards|concepts`, `log/*/*`,
  `feedback/*`. Clear: `meta`, `rev`, `migration`, `requests/*/claim`,
  `sessions/*/progress/rid`. Any other write is refused (fail closed); a
  write never lands inside a unit. Tables: `tutor/relay/e2e.py`,
  `app/lib/sync/e2e_seal.dart`; parity vectors `contract/e2e_vectors.json`.
- A unit that does not open reads as absent; a unit without `_e2e` (legacy
  plaintext) is accepted.
- Locked (no or wrong password): the worker retries its startup and writes
  nothing; the app shows only the lock button (icon) and a retry.
- Migration: the worker, once (`migration/v1_copied_at`), first raises
  `tutor/v1/meta.min_client` to 2 (pre-e2e apps stop), then patches in the
  RTDB-canonical nodes the new root lacks: `log`, `prefs`, `feedback`,
  `sessions/*/user`. Projections are re-published from its files.
  `tutor/v1` is never deleted.
