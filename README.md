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
written if one fails. Ids are never editable and nothing is deleted. The repo
deck JSON is edited by hand (the old page's deck editor was retired
2026-10-12 with the page).

## Licence

- The code is under the MIT licence (`LICENSE`).
- The card text is under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/),
  because many excerpts are quoted from Wikipedia.
- Every other excerpt is a short attributed quotation that stays its
  owner's. Each card links to its source.
