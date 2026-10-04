# Project Horae waitlist

The root site remains static GitHub Pages (main, repository root, .nojekyll).
The independent API is Python 3.12+ / standard library SQLite; no packages,
custom image, email sending, payment integration, or public subscriber reads.

## Easypanel service contract

- Native **Nixpacks** app, Git repository backmeupplz/project-horae, branch main,
  build context/root **/waitlist**. Its requirements.txt triggers Python detection;
  nixpacks.toml starts **python server.py**. .python-version selects Python 3.12.
- **One replica**, stop-first updates, persistent local Easypanel volume mounted
  at **/data**. Do not deploy without the mount or scale this SQLite app across
  hosts/replicas. Keep the same volume across restarts/redeploys.
- Internal HTTP port **3000**, behind Easypanel's HTTPS reverse proxy only.
  No host-published app port. Health check **GET /health** returns 200 with
  {"status":"ok"} when the database is readable; 503 on database errors.
  This is a readiness check, not proof of writable disk or Telegram delivery.
- Planned public hostname: **https://horae-waitlist.borodutch.com**. Frontend
  action: **https://horae-waitlist.borodutch.com/api/waitlist**. Configure DNS/TLS
  and verify the actual service/domain before release; this document does not
  assert an infrastructure deployment has happened.
- Environment: PORT=3000 and DATABASE_PATH=/data/waitlist.sqlite3 (defaults).
  **TELEGRAM_BOT_TOKEN** and **TELEGRAM_CHAT_ID** are supplied manually by the
  owner in Easypanel. Do not put either in Git, the site, shell history or logs.
  Restart/redeploy after changing environment. Until both are present, signups
  succeed and outbox rows remain pending with zero attempts. Live Telegram
  delivery is **unverified until manually configured and checked**.
- Run behind the reverse proxy; the bounded stdlib server is not intended as a
  directly exposed general-purpose web server. Configure proxy request timeouts
  and body limits as additional protection; do not enable request-body logging.

## API and privacy

POST /api/waitlist requires Content-Type: application/json, a Content-Length
of 1–2048 bytes, and one exact Origin: https://projecthorae.com or
https://www.projecthorae.com. OPTIONS supports only POST / Content-Type.
No credentials/cookies. Rejects missing, null, alternate, or suffix origins.
CORS is a browser restriction, **not authentication or bot prevention**.

Body: {"email":"a.b+tag@example.com","website":""}. Email is trimmed and
lowercased, limited to 254 ASCII characters, 64 local-part characters and
valid domain labels. Dots and plus tags are preserved. Quoted local parts and
internationalized addresses are deliberately unsupported. No deliverability
claim is made. The optional website honeypot silently accepts but discards
filled submissions. Other fields/invalid types are rejected.

New and duplicate addresses both receive 200 {"ok":true}; only a new insert
creates an outbox row. 400 invalid input, 403 origin, 413 size, 415 content type,
429 rate limit, 503 failed storage (safe to retry). 429/503 include Retry-After.
No response includes an email. GET /api/waitlist and exports are not available.

The database stores normalized email and UTC signup timestamp. Application
request logging is disabled; failure logs do not include addresses, tokens,
request URLs, payloads or raw exception details. Owner notification includes
email/time, in Telegram plain text (no parse_mode). No announcements are sent.

Limits: 32 concurrent HTTP handlers, 5-second socket timeout, 32 queued sockets,
30 POSTs/minute per **socket peer**, 120/minute overall, bounded peer map.
Forwarded/X-Forwarded-For headers are **ignored**. Behind Easypanel, users often
share one proxy peer and therefore the 30/minute allowance; this conservative
limit is intentional for a small waitlist. Rate windows reset on process restart.
For larger traffic, add edge throttling/trusted-proxy identification after
verifying the proxy network; never blindly trust caller-supplied IP headers.

## Durable delivery

SQLite WAL and synchronous=FULL commit the unique signup and its outbox row
in the **same transaction**, before the success response. Outbox claims use an
atomic transaction with a 120-second lease and random ownership token. Claims
consume an attempt before network I/O; abandoned leases become eligible after
expiry. Old owners cannot update a newer lease. One serial worker processes
at most one notification/second, HTTP timeout 15 seconds, bounded response size,
no credential-bearing redirects. Retries start at 30 seconds, double to a
one-hour ceiling, and honor the larger of Telegram's Retry-After header/date
and JSON parameters.retry_after as a minimum delay **after the attempt ends**.
Eight attempts maximum, including crashed attempts; exhausted jobs stay in the
DB with failed_at for protected operator inspection. No automatic reset loop.
Missing bot variables consume **no** attempts.

**Not exactly once:** Telegram may accept a message before a response is lost
or before the delivery commit. A later retry may send a duplicate notification.
Likewise a crash on the last attempt may leave delivery uncertain. Signup
records stay unique and durable regardless. Do not retry delivered jobs just
to test the bot. Monitor failed/pending counts through protected access.

## Protected backup, export and recovery

Use authenticated Easypanel service console or authorized SSH access to the
mounted volume. Never create a public download/export endpoint or copy data
into the repository/GitHub Pages tree. Restrict operator files (umask 077),
transfer backups via protected SSH, retain them in access-controlled backup
storage, and test restoring a copy. No subscriber content belongs in ticket
comments, shared logs, or screenshots.

For a consistent live backup use SQLite's backup API, **not** a copy of only
the .sqlite3 file while WAL writes are active. Example inside the service's
protected console (choose a private destination on the volume):

    umask 077
    python - <<'PY'
    import sqlite3
    with sqlite3.connect('/data/waitlist.sqlite3') as source:
        with sqlite3.connect('/data/waitlist-backup.sqlite3') as target:
            source.backup(target)
    PY

Export from that backup in a protected operator directory, never stdout:

    python - <<'PY'
    import csv, os, sqlite3
    os.umask(0o077)
    with sqlite3.connect('/data/waitlist-backup.sqlite3') as db:
        with open('/data/waitlist-export.csv', 'x', newline='') as output:
            writer = csv.writer(output)
            writer.writerow(['email', 'created_at'])
            writer.writerows(db.execute('SELECT email, created_at FROM signups ORDER BY id'))
    PY

Treat the CSV as untrusted data: email local parts can start with formula
characters; import columns explicitly as text, never blindly open in a
spreadsheet with formula evaluation. Export does not authorize bulk mailing.

Inspect counts only (e.g. pending/failed outbox rows) through SQLite in the
protected console. After correcting a bot outage, an operator may explicitly
reset selected failed rows' attempts/failed_at/lease/next_attempt, accepting the
ambiguous-duplicate caveat. Do not blanket-reset delivered rows. To restore,
stop the app through Easypanel, preserve the old volume files, restore a checked
consistent backup (including outbox state, with no stale WAL files from the old
database), then restart one replica and verify health/counts. Restoring an older
backup may lose newer signups and repeat notifications; choose the recovery
point deliberately. Never delete the persistent volume during routine updates.

## Checks

From the repository root:

    python3 -m unittest discover -s waitlist -v
    node --test tests/waitlist.test.cjs
    git diff --check

CI runs these on PRs and pushes to main. Tests use temporary DBs, local HTTP and
mocked Telegram only. They cover concurrent duplicates, transactional rollback,
restart/lease recovery, finite retries/Retry-After, missing config, input/CORS,
rate limiting and frontend loading/success/error/retry/timeout feedback. No real
bot call is part of tests. Node tests use a DOM stub, not a visual browser test.

Release verification: check site form and API TLS/CORS/health, submit a reserved
synthetic example.com address twice, inspect protected DB counts (one signup,
one outbox), restart via Easypanel and recheck persistence. Keep bot variables
unset for synthetic acceptance tests. Verify mobile/keyboard form rendering.
Only then, when the owner supplies both variables, independently verify a
single permitted notification; distinguish this from the mock contract tests.
