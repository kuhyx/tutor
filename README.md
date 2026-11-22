# tutor

A local tutor that teaches source-checked cards in conversation. Its client
is the Flutter app in `app/` (phone, and on the PC the web build at
`127.0.0.1:8778/app/`; `/` redirects there), talking to this server over a
Firebase relay (`DOCS-relay.md`). The server walks one card at a time through a Claude conversation
(claude-agent-sdk over the logged-in `claude` CLI, no API key), and writes a
signed earned-time credit row for every active study block. Minutes past a
day's quota are banked (up to 100) and paid out on later days by the live
worker as `carry-<day>` rows (`DOCS-contract-carry.md`).

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
it has Claude Code's local tools with permissions bypassed (the ones that act
through the claude.ai account, `research.BLOCKED_TOOLS`, and remote subagents
are off), so its CLI runs
inside bubblewrap (`scripts/tutor_model_sandbox.sh`, set as the SDK's
`cli_path` by `tutor/research.py`). It sees `/usr`, a short list of `/etc`
files and a scratch HOME it may install into; never the data dir, the
ledger key, the releases, the repo or `~/.claude`. Its network is pasta's
(`passt`): the internet, but nothing on this machine (no loopback services
such as :8778, no X server socket) and no private network: an nftables fence
inside pasta's namespace (`scripts/tutor_model_netfence.sh`) refuses RFC1918,
the tailnet (100.64/10), link-local, IPv6 ULA and link-local and the host's
own addresses, except port 53 to the resolvers in `/etc/resolv.conf`.
`install.sh` installs bwrap, pasta and nftables. Its login is a
copy of the Claude access token only (`tutor/model_login.py`), refreshed on
the host before each turn. Each turn has 90 s of tool time; later calls are
refused and the tutor answers with what it has. Card generation, drills and
the other model calls keep no tools (`session.isolated_options`).

A sandbox that will not start (the wrapper or the fence names itself on the
CLI's stderr, `tutor_model_netfence: ...`) is filed on the shared app-errors
board (`tutor/model_fault.py`: spool `~/.local/state/app-errors-spool/tutor.jsonl`,
kind `model.sandbox`, repo `kuhyx/tutor`) and shows one icon-only critical
`notify-send` toast (restart icon, no words) per failure streak, until a model
call succeeds again. Every other model failure is filed as `model.error`, no
toast; API outages are not filed.

## Agent E2E

`scripts/e2e_sandbox.sh` lets an agent click through the real web app
against the real engine and relay without touching live state. It copies
`~/.local/share/tutor` into a `mktemp` dir. The copy has no ledger, a
throwaway key and a fresh device id; the live id is rewritten. The relay
talks to a local Firebase RTDB emulator (the cached
`firebase-database-emulator` jar), never the real database, and the server
uses a free port, never :8778. The app reaches the emulator over plain
HTTP/1.1, as it reaches the real database (which never negotiates h2), so
Chrome's 6 connections per host are the same budget as in production; the
app holds at most 4 streams (DOCS-contract §9). The app build is
`app/tool/e2e/main.dart`: the real services pointed at the emulator, with
semantics on so the driver can find buttons by label. The driver (`scripts/e2e_drive.py`) runs Chromium
over `--remote-debugging-pipe` on the Xvfb `:97`. It taps buttons, checks
the outcome in the emulator (the request result, `live.card`, the first
tutor message, F3's reply trace and Thinking panel) and saves
`app/build/screens/e2e_<flow>_*.png`. Model calls are real, and a tutor turn
(high effort, thinking, up to 90 s of research) can outlast 60 s, so F1, F3
and F4 run as three calls: `send` (taps up to the request), `wait` (polls the
emulator for up to 45 s; exit 75 = still pending, call it again) and `check`
(reopens the app and asserts). Each command fits in 60 s:

```bash
scripts/e2e_sandbox.sh build                                    # after app changes (~25 s)
scripts/e2e_sandbox.sh up --as-of "2026-10-17 22:00"            # F1 sandbox
scripts/e2e_sandbox.sh flow F1 send   # Continue learning; then `flow F1 wait`, `flow F1 check`:
                                        # E2E_CARD (vhost-what) + tutor message
scripts/e2e_sandbox.sh up --as-of "2026-10-20 17:24:30"         # E2E_SESSION at card end
scripts/e2e_sandbox.sh flow F3 send   # card end: a follow-up (then wait, check): answered,
                                        # with a trace and Thinking panel; credit goes on
scripts/e2e_sandbox.sh flow F4 send   # Stop here, History -> "Ask a follow-up" (then wait,
                                        # check): answered
scripts/e2e_sandbox.sh up --struggle --as-of "2026-10-20 17:24:30"  # F5: 2 Again seeded
scripts/e2e_sandbox.sh flow F5 send   # Review (N due) -> Again -> "Get help" (then wait,
                                        # check): struggle start + rule 16; untaught refused
scripts/e2e_sandbox.sh up --as-of "2026-10-24 20:00" --carry 130  # F6: fake clock, 130 min
scripts/e2e_sandbox.sh flow F6         # carry-<day>-m<n> row, stats, "Banked B min · prepaid P"
scripts/e2e_sandbox.sh restart         # a second worker start on the same sandbox
scripts/e2e_sandbox.sh flow F6 again   # the ledger is unchanged: no duplicate carry row
scripts/e2e_sandbox.sh up                                       # F7: the desktop Focus screen
scripts/e2e_sandbox.sh flow F7   # project, no subjects -> Start -> notification click (no
                                   # check-in) -> "Still working" tap -> Stop; activity.jsonl
                                   # in <sandbox>/focus (never the live dir)
scripts/e2e_sandbox.sh up --nocard due                        # F12: no card left (or `review`
scripts/e2e_sandbox.sh flow F12  # with E2E_SUBJECT=how-a-car-works): result `kind` +
                                   # `error` + `next`; the app speaks its own line (DOCS-relay-kinds.md)
scripts/e2e_sandbox.sh flow F9   # fresh `up` each: check-in card at 421 s, rated -> tutor/heartbeat
scripts/e2e_sandbox.sh flow F10  # card rated at 650 s (lapsed) -> start, start; still graded
scripts/e2e_sandbox.sh flow F19  # fresh `up`: archive a subject on Home, then undo it
scripts/e2e_sandbox.sh up --gate   # F21 (no --as-of: a model turn): 2 unpassed cards hold N
scripts/e2e_sandbox.sh flow F21 send  # Continue -> review opens, "2 left" -> Good x2 -> Next
                                        # goes out by itself (then wait, check): N's card live
scripts/e2e_sandbox.sh down
```

`--as-of` (`HH:MM` or `HH:MM:SS`) rewinds the copy to a reported moment:
later log events, transcripts and drill logs are dropped, and so are the
later events of an earlier transcript. The sandbox worker runs under
libfaketime from that moment (its "today"), past or future; the app and
the emulator keep the real clock. `--gate` (`scripts/e2e_gate.py`) teaches every card
before the subject's first unstarted module N, reviews them Good, and leaves the
last two of the module before N unpassed; it checks the worker's own pick agrees.
`--struggle` (`scripts/e2e_seed.py`) gives the subject's first due card two
Again ratings from a fresh device, so F5's Again in the app is the third and
Review offers help; `<sandbox>/f5_seed.json` names the card and a known
untaught one. `--carry N` signs N minutes ending the day before the worker's
today into the sandbox ledger with the sandbox's throwaway key. The server
logs every system prompt to `<sandbox>/prompts.jsonl`, where F5 finds rule
16. F5's opening turn is one real model turn, as F1's; F6 calls no model. A flow exits 0 on PASS. Otherwise it prints
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

### Pinned subjects

Put `https://` URLs in a new subject's text and the tutor writes that
subject's cards from those pages only. It never searches Wikipedia for
them. Example: `Product and design taste: https://paulgraham.com/taste.html
https://paulgraham.com/ds.html`. The planner reads each page's title and
opening words. For every module, the model keeps the pages that cover it, and
the cards quote one of them (`tutor/curriculum/webpages.py`). If a page cannot
be fetched or has under 1500 characters of text, the draft fails and names
that URL.

### Who writes and who asks

Two model tiers (`tutor/tiers.py`). Fable 5.2 at `xhigh` effort writes the
cards of a new module, once, and with them an interrogation path per card:
an opening question, probes, the likely misconception, a hint ladder, the
pass criterion, and whether a typed follow-up after a correct pick adds
anything. Sonnet at `high` effort leads the session, rewrites a card you ask
to change and drafts plans. The tutor reads a card's path before its first
question as suggestions and leaves it whenever you do. Paths stay on the PC
(`subjects/<id>/paths.json`) and are never shown. If Fable is unavailable a
new module fails and **Approve** retries it; Sonnet never writes it instead.

Every drafted or edited card must pass seven rules
(`tutor/curriculum/quality.py`): one question per card; no unguessable name
or number; an abbreviation card asks only for the expansion and carries a
mnemonic; one term per card; a maths card answers with the formula; nothing
subjective or hedged; a card you found hard carries a mnemonic.

### Redraft

`python -m tutor redraft start` drafts every module's cards again with
Fable, archived subjects too. It backs up `subjects/` to
`~/.local/share/tutor/backups/subjects-<time>/` first. The running server
then works through the modules and waits whenever a reply to you is in
flight. A new card that Fable matches to an old one keeps the old id, your
taught state and its due date; an old card with no match is suspended, never
deleted; a module with more than 12 cards is cut into several. `status`
lists the modules (exit 75 while any is pending). `report` writes
`~/.local/state/tutor/redraft/<time>/report.md`: your flagged cards before
and after, rule violations per subject, the suspended cards and any module
that could not be redrafted. To rehearse on a copy: `start --data DIR`, then
`drain --data DIR`.

## Evening gate

`python3 -m tutor.gate --production --evening` is the tutor rung of the evening
chain (`gatelock.evening_chain`). Paid today (`earned_time.credit_units(TUTOR)`
reaches `max_units`, quota 15 / 30 / 50 minutes by weekday): exit 0, no window.
No X within 10 s: exit 3. Otherwise a HARD gatelock window (arbiter rank 150)
shows minutes against the quota as a segmented bar, with two controls that work
from t=0: open the tutor (study mode: the grab comes down, the page
`http://127.0.0.1:8778/app/` opens, a strip stays on top, "back" re-grabs; no
timeout, like leetcode-guard) and end the evening (exit 10). The credit landing
closes it (exit 0) within ~3 s. Read-only: it never writes the ledger. No words
on screen (textgate).

It runs under `/usr/bin/python3`, so `tutor` must import there without the
venv. The gate modules (`gate*.py`) need only stdlib, `gatelock` and
`earned_time`; `tutor/__init__.py` is empty. Install (system python, no deps,
editable from this checkout, as book-guard):

    /usr/bin/python3 -m pip install --user --break-system-packages --no-deps -q -e ~/src/tutor

Verify: `cd / && /usr/bin/python3 -c 'import tutor.gate'`. The tutor server
keeps running from its own venv; this install does not touch it.

E2E (private Xvfb 3840x2160, scratch HOME, tmp signed ledger and key, fake
`xdg-open`, mtime canary on the live ledger): `scripts/e2e_evening_gate.sh up`,
then one of `paid | nox | credit | end | study | study-credit` per call,
`canary`, `down`. Screenshots land in `~/data/claude-scratch/e2e/tutor/shots/`.

## Licence

- The code is under the MIT licence (`LICENSE`).
- The card text is under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/),
  because many excerpts are quoted from Wikipedia.
- Every other excerpt is a short attributed quotation that stays its
  owner's. Each card links to its source.
