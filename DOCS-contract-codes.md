# Machine codes beside the sentences (contract §4a)

Split out of `DOCS-contract.md` §4a (the contract wins on any conflict).

The app is text-free: it paints a glyph per machine code and keeps the
server's sentence only as the spoken label. Every vocabulary is closed and
lives in `tutor/codes.py`; `contract/codes.json` is its golden copy, tested
against both `tutor/codes.py` and the Dart mirror `app/lib/model/codes.dart`.
A client maps a missing or unknown value to `other` (the generic glyph);
adding a value is a contract change. All additive: every sentence field stays.

| surface | field | vocabulary |
|---|---|---|
| failed result | `code` | `relay_code` (§4 codes) |
| failed result | `reason` | `fail_reason`: `paste_statement` (`bad_request` of `lc_open`), `rate_limit`/`overloaded`/`network` (`claude_unavailable`); anything else is sent as `other` |
| failed result, subject `meta`, plan module, `cardgen` result | `error_kind` | `error_kind`: `claude_limit`/`claude_overloaded`/`claude_network` (outage), `model_failed`, `sources_missing`, `too_few_cards`, `bad_request`, `other`; set by exception type (`codes.error_kind`), null/absent with no `error` |
| tutor message | `notice_kinds` | `notice_kind`, same index as `notices` (`removed`, `added`, `updated`, `split`, `mnemonic_set`, `mnemonic_cleared`); absent on older messages |
| session `clock` | `paused_reason` | `pause_reason`: the two fixed sentences (`clock.LOW_EFFORT`, `clock.STALLED`) |
| claim | `phase` | `relay_phase`, the 5 phases in order; an unknown phase gets a neutral glyph |
| `unavailable` / `claude_unavailable` | `reason` | `unavailable_reason` (`unavailable.REASONS`; a window with another reason is never read back) |
