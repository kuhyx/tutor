# tutor

A local tutor that teaches source-checked cards in conversation. Its client
is the Flutter app in `app/` (phone, and on the PC the web build at
`127.0.0.1:8778/app/`; `/` redirects there), talking to this server over a
Firebase relay (`DOCS-relay.md`). The server walks one card at a time through a Claude conversation
(claude-agent-sdk over the logged-in `claude` CLI, no API key), and writes a
signed earned-time credit row for every active study block.

Extracted from [plc-lab](https://github.com/kuhyx/plc-lab) with its history.
The only subject so far is `subjects/automation/`: the PLC / OT security deck.

## Run

```bash
scripts/setup_dev.sh   # .venv with tutor (editable) + test/lint tools
./install.sh           # once: install + enable tutor.service (starts at boot)
./run.sh               # open the desktop app (127.0.0.1:8778/app/; starts it if down)
./run.sh --no-open     # start it if needed and print the URL only
```

The live server never runs from the working tree. `scripts/tutor_deploy.sh`
copies a release into `~/.local/lib/tutor-live/releases/`,
smoke-tests it on a scratch port against a copy of today's sessions, waits
until no reply is in flight, then points `current` at it and restarts
`tutor.service`. The session resumes from its transcript. The unit
(`systemd/tutor.service`, installed by `install.sh`) runs
`~/.local/lib/tutor-live/current` with the relay on, is enabled under
`default.target` and restarts on failure, so the phone finds the PC online
after a reboot. `scripts/tutor_launch.sh` starts only the deploy's scratch
smoke-test server, in its own `systemd-run --user` unit.

| What | Where |
| --- | --- |
| sessions, transcripts | `~/.local/share/tutor` (`TUTOR_DATA`) |
| earned-time ledger | `~/.local/share/tutor/ledger.json` |
| server log | `~/.local/state/tutor/server.log` |
| releases | `~/.local/lib/tutor-live` (fixed: `tutor.service` runs its `current`) |
| the model's sandbox | `~/.cache/tutor/sandbox` (`TUTOR_MODEL_SANDBOX`; under `TUTOR_DATA` when that is set) |

## The model's sandbox

The tutor conversation may research (web search and fetch, code, subagents):
it has every Claude Code tool with permissions bypassed, so its CLI runs
inside bubblewrap (`scripts/tutor_model_sandbox.sh`, set as the SDK's
`cli_path` by `tutor/research.py`). It sees `/usr`, a short list of `/etc`
files, the network and a scratch HOME it may install into; never the data
dir, the ledger key, the releases, the repo or `~/.claude`. Its login is a
copy of the Claude access token only (`tutor/model_login.py`), refreshed on
the host before each turn. Each turn has 90 s of tool time; later calls are
refused and the tutor answers with what it has. Card generation, drills and
the other model calls keep no tools (`session.isolated_options`).

## Agent E2E

`scripts/e2e_sandbox.sh` lets an agent click through the real web app
against the real engine and relay without touching live state. It copies
`~/.local/share/tutor` into a `mktemp` dir. The copy has no ledger, a
throwaway key and a fresh device id; the live id is rewritten. The relay
talks to a local Firebase RTDB emulator (the cached
`firebase-database-emulator` jar), never the real database, and the server
uses a free port, never :8778. The app build is `app/tool/e2e/main.dart`:
the real services pointed at the emulator, with semantics on so the driver
can find buttons by label. The driver (`scripts/e2e_drive.py`) runs Chromium
over `--remote-debugging-pipe` on the Xvfb `:97`. It taps buttons, checks
the outcome in the emulator (the request result, `live.card`, the first
tutor message) and saves `app/build/screens/e2e_<flow>_*.png`. Model calls
are real. Each command fits in 60 s:

```bash
scripts/e2e_sandbox.sh build                                    # after app changes (~25 s)
scripts/e2e_sandbox.sh up --as-of "2026-10-17 22:00"            # F1 sandbox
scripts/e2e_sandbox.sh flow F1   # Continue learning -> E2E_CARD (vhost-what) + tutor message
scripts/e2e_sandbox.sh up --new-cap 10 --as-of "2026-10-17 22:00"
scripts/e2e_sandbox.sh flow F2   # daily cap -> "Learn more anyway" -> E2E_CARD
scripts/e2e_sandbox.sh down
```

`--as-of` rewinds the copy to a reported moment: later log events,
transcripts and drill logs are dropped. `--new-cap N` adds a Settings
`new_cap` event. A flow exits 0 on PASS. Otherwise it prints
`FAIL <flow> step N: ...`, the page's console errors and a `_fail.png`.

## The deck

`subjects/automation/deck/<topic>.json` holds the cards, one array per topic
(`tutor.cards.TOPICS`). Each card has:

- `source`: the URL it was written from.
- `excerpt`: verbatim text from that page that supports the answer.
- optionally `requires`: ids of cards that must be done first. The tutor
  keeps such a card locked until then.

The answers are paraphrased. Only the excerpt is quoted, and it is shown with
a link to its source. `tutor.sources` fetches each source once into
`~/.cache/plc-lab/sources`, reduces it to plain text (PDFs go through
`pdftotext`) and requires the excerpt to appear in it.

Cards are edited in the app's **Edit cards** screen (`card_edit` over the
relay, `DOCS-contract-curriculum.md`): the same card checks, and nothing is
written if one fails. The tutor itself may also fix, add or remove (suspend)
a card mid-session, with a notice line in the chat (`DOCS-contract-curriculum.md`
§3). Ids are never editable and nothing is deleted. The repo
deck JSON is edited by hand (the old page's deck editor was retired
2026-10-12 with the page).

## Licence

- The code is under the MIT licence (`LICENSE`).
- The card text is under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/),
  because many excerpts are quoted from Wikipedia.
- Every other excerpt is a short attributed quotation that stays its
  owner's. Each card links to its source.
