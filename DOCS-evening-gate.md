# Evening gate (`tutor/gate.py`)

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
