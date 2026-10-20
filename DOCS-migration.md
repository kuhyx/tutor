# Tutor contract: the one-off v1 migration

Split out of `DOCS-contract.md` §11 (the contract wins on any conflict).

## 11. Migration (A2/B; one-off `python -m tutor migrate [--data DIR]`, idempotent)
- Data dir `~/.local/share/automation_tutor` -> `~/.local/share/tutor`; old
  kept read-only.
- `deck/*.json` (7 topics, 167 cards) -> `subjects/automation/` seed: subject
  `automation`, plan rev 1 `approved`; modules = `cards.TOPICS` in order,
  keeping `prefixes`; module `requires` = topics named by cross-topic card
  `requires` into EARLIER topics (forward ones, e.g. `fund-five-languages`,
  stay card-level only); card `requires` kept; cards `origin:"seed"`, rev 1;
  modules `ready`. Card-level gating (`gating.py`) kept.
- `progress.json`: `cards_done` (14) -> `taught` events in the worker log (`at`
  = recorded time, session); `mastered` (46) -> `subjects/automation/concepts`;
  `archived` -> `sessions/{sid}/user`; `repairs` stays local. Modules with any
  taught card are unlocked regardless of recall (grandfather).
- `sessions/*.jsonl` (18) keep sids; projection published via replay
  (`history.session_view`). Old images: resolve `url` from `page_url` via
  Commons `imageinfo`, else attribution only. Old diagrams: inline SVG from the
  tutor-diagrams cache by filename, else dropped.
- No FSRS/Anki history imported; taught cards start FSRS at taught time.
- Cutover only via the deploy script with the worker drained (no new claims,
  leases finished).
