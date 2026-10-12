# tutor

A local tutor that teaches source-checked cards in conversation. It serves a
page on `127.0.0.1`, walks one card at a time through a Claude conversation
(claude-agent-sdk over the logged-in `claude` CLI, no API key), and writes a
signed earned-time credit row for every active study block.

Extracted from [plc-lab](https://github.com/kuhyx/plc-lab) with its history.
The only subject so far is `subjects/automation/`: the PLC / OT security deck.

## Run

```bash
scripts/setup_dev.sh   # .venv with tutor (editable) + test/lint tools
./run.sh               # open the tutor on 127.0.0.1:8778 (starts it if down)
./run.sh --no-open     # start it if needed and print the URL only
```

The live server never runs from the working tree. `scripts/tutor_deploy.sh`
copies a release into `~/.local/lib/tutor-live/releases/`,
smoke-tests it on a scratch port against a copy of today's sessions, waits
until no reply is in flight, then swaps it in. The session resumes from its
transcript. `scripts/tutor_launch.sh` starts a release in its own
`systemd-run --user` unit, so the server outlives whatever started it.

| What | Where |
| --- | --- |
| sessions, transcripts | `~/.local/share/tutor` (`TUTOR_DATA`) |
| earned-time ledger | `~/.local/share/tutor/ledger.json` |
| server log | `~/.local/state/tutor/server.log` |
| releases | `~/.local/lib/tutor-live` (`TUTOR_LIVE_ROOT`) |

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

The **Edit cards** view (side panel, or `#edit` in the URL) edits a card's
front, back, source, excerpt and `requires`, or adds a card to a topic. Ids
are never editable and nothing is deleted. A save runs the card checks and the
250-line cap, and writes nothing if one fails. It writes the repo deck
(`TUTOR_DECK_SRC`, which `run.sh` and `scripts/tutor_deploy.sh`
set) and the live release's own copy. Without the variable the view is
read-only.

## Licence

- The code is under the MIT licence (`LICENSE`).
- The card text is under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/),
  because many excerpts are quoted from Wikipedia.
- Every other excerpt is a short attributed quotation that stays its
  owner's. Each card links to its source.
