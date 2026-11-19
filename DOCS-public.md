# Public hostname (phone on mobile data)

`https://tutor.kuhy.duckdns.org` reaches the same server as `127.0.0.1:8778` through the `gitea-caddy` edge
(`~/services/gitea/sites/tutor.kuhy.duckdns.org.caddy`, written by
`linux_configuration/features/publish_caddy_site.sh tutor 8778`). The server still binds loopback only. A phone
that is not paired gets 401 for every request. Code: `tutor/device_gate.py`, `tutor/local_guard.py`,
`tutor/webapp.py`; tests `tutor/tests/test_device_gate.py`. Same design as the todoImplementer board
(`todoImplementer/DOCS-phone.md`).

## Local or public: the Host header

Caddy and the PC browser both reach the server from 127.0.0.1, and `X-Forwarded-*` is written by the sender, so the
`Host` header is the only signal. A loopback origin of the bound port is local (nothing changes). Exactly
`$TUTOR_PUBLIC_HOST` (default `tutor.kuhy.duckdns.org`; empty turns the public name off) is public. Any other Host
stays 403. Never rewrite Host in Caddy (`header_up Host`): the PC-only routes would then look local.

## What a public request may do

- Unpaired: 401, except `GET /pair?c=<code>` (the code is the credential).
- Paired (cookie `tutor_device`): `GET`/`HEAD` of `/`, `/app`, `/app/*` only. Everything else is 403: `/api/*` (it
  runs Claude), `/media/*`, every POST, every websocket. The page needs nothing more: it talks to the engine over
  the Firebase relay.
- `/app/sync-credentials` and `/app/sync-passphrase` (the web page's sign-in, `tutor/webapp.py`) are served to a
  paired phone's own page on every load, without using up the desktop's one serve per process. This hands the
  Firebase session and the e2e passphrase to a paired phone, the same trust as the phone app holding them.

## Pairing

`scripts/tutor_pair.sh` asks the server (`POST /api/pair`, loopback only) for a code (single use, 300 s, at most 5
pending, in server memory, a restart drops them) and prints `https://tutor.kuhy.duckdns.org/pair?c=<code>` plus a
QR. `scripts/tutor_pair.sh --adb` opens the link on a USB phone. The phone's `GET /pair` answers 303 to `/` with
`tutor_device=<token>; Max-Age=34560000; Path=/; Secure; HttpOnly; SameSite=Lax` (400 days, no renewal: pair again
after that). A bad, used, expired or missing code is 403.

## Devices

`~/.config/tutor/devices.json` (`$TUTOR_DEVICES`), mode 0600, a JSON list of `{sha256, created, ua}`; the token is
never stored. Read on every public request, so edits apply at once. Missing or malformed file: nobody is paired.
Revoke every phone: delete the file. One phone: remove its row.
