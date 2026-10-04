"""Single-replica waitlist API. Python standard library only."""
from contextlib import contextmanager
import email.utils
import json
import logging
import math
import os
from pathlib import Path
import re
import signal
import socket
import sqlite3
import threading
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ORIGINS = frozenset({"https://projecthorae.com", "https://www.projecthorae.com"})
MAX_BODY = 2048
MAX_ATTEMPTS = 8
LEASE_SECONDS = 120
LOG = logging.getLogger("waitlist")


def normalize_email(value):
    if not isinstance(value, str) or len(value) > 320:
        raise ValueError("Invalid email")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("Invalid email")
    value = value.strip().lower()
    if not value.isascii() or len(value) > 254 or value.count("@") != 1:
        raise ValueError("Invalid email")
    local, domain = value.split("@")
    if (not 1 <= len(local) <= 64 or local.startswith(".") or local.endswith(".")
            or ".." in local or not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+", local)):
        raise ValueError("Invalid email")
    labels = domain.split(".")
    if len(labels) < 2 or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels):
        raise ValueError("Invalid email")
    return value


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS signups (
                    id INTEGER PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS outbox (
                    signup_id INTEGER PRIMARY KEY REFERENCES signups(id),
                    attempts INTEGER NOT NULL DEFAULT 0,
                    next_attempt REAL NOT NULL DEFAULT 0,
                    lease_until REAL NOT NULL DEFAULT 0,
                    lease_token TEXT,
                    delivered_at TEXT,
                    failed_at TEXT
                );
                CREATE TABLE IF NOT EXISTS telegram_cooldown (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    until REAL NOT NULL DEFAULT 0
                );
                INSERT OR IGNORE INTO telegram_cooldown(id) VALUES (1);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        try:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("PRAGMA foreign_keys=ON")
            with db:
                yield db
        finally:
            db.close()

    def signup(self, email):
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            row = db.execute("INSERT INTO signups(email, created_at) VALUES (?, ?) ON CONFLICT(email) DO NOTHING RETURNING id", (email, now)).fetchone()
            if row:
                db.execute("INSERT INTO outbox(signup_id) VALUES (?)", (row[0],))
        return bool(row)

    def health(self):
        with self.connect() as db:
            db.execute("SELECT 1 FROM signups LIMIT 1").fetchall()

    def claim(self, now):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT until FROM telegram_cooldown WHERE id=1").fetchone()[0] > now:
                return None
            # A crash after the final claim still ends in a terminal state.
            db.execute("UPDATE outbox SET failed_at=? WHERE attempts>=? AND lease_until<=? AND delivered_at IS NULL AND failed_at IS NULL", (datetime.fromtimestamp(now, timezone.utc).isoformat(), MAX_ATTEMPTS, now))
            row = db.execute("SELECT o.signup_id, s.email, s.created_at, o.attempts FROM outbox o JOIN signups s ON s.id=o.signup_id WHERE o.delivered_at IS NULL AND o.failed_at IS NULL AND o.attempts<? AND o.next_attempt<=? AND o.lease_until<=? ORDER BY o.signup_id LIMIT 1", (MAX_ATTEMPTS, now, now)).fetchone()
            if row is None:
                return None
            token = uuid.uuid4().hex
            db.execute("UPDATE outbox SET attempts=attempts+1, lease_until=?, lease_token=? WHERE signup_id=?", (now + LEASE_SECONDS, token, row[0]))
            return (*row, token)

    def finish(self, job, now, success, retry_after=0):
        signup_id, _, _, previous_attempts, token = job
        attempt = previous_attempts + 1
        stamp = datetime.fromtimestamp(now, timezone.utc).isoformat()
        # Server Retry-After is a floor, not a hint to retry sooner.
        delay = max(min(3600, 30 * 2 ** (attempt - 1)), retry_after)
        with self.connect() as db:
            db.execute("UPDATE outbox SET delivered_at=?, failed_at=?, next_attempt=?, lease_until=0, lease_token=NULL WHERE signup_id=? AND lease_token=?", (stamp if success else None, stamp if not success and attempt >= MAX_ATTEMPTS else None, now + delay, signup_id, token))
            if not success and retry_after > 0:
                # A Telegram limit applies to every job, even if this lease expired.
                db.execute("UPDATE telegram_cooldown SET until=MAX(until, ?) WHERE id=1", (now + retry_after,))


class DeliveryError(Exception):
    def __init__(self, retry_after=0):
        self.retry_after = retry_after


def retry_seconds(value, now):
    try:
        seconds = float(value)
        return max(0, seconds) if math.isfinite(seconds) else 0
    except (TypeError, ValueError):
        try:
            return max(0, email.utils.parsedate_to_datetime(value).timestamp() - now)
        except (TypeError, ValueError, OverflowError):
            return 0


def send_telegram(token, chat_id, email_address, created_at):
    payload = json.dumps({"chat_id": chat_id, "text": f"New Project Horae waitlist signup\nEmail: {email_address}\nSigned up (UTC): {created_at}"}).encode()
    request = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=payload, headers={"Content-Type": "application/json"}, method="POST")
    # Do not follow redirects carrying bot credentials or subscriber data.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args):
            return None
    opener = urllib.request.build_opener(NoRedirect)
    try:
        response = opener.open(request, timeout=15)
    except urllib.error.HTTPError as error:
        response = error
    except (OSError, urllib.error.URLError):
        raise DeliveryError() from None
    with response:
        retry_after = retry_seconds(response.headers.get("Retry-After"), time.time())
        try:
            body = json.loads(response.read(16385))
            if not isinstance(body, dict):
                raise ValueError()
        except (ValueError, OSError):
            raise DeliveryError(retry_after) from None
        parameters = body.get("parameters")
        if isinstance(parameters, dict):
            retry_after = max(retry_after, retry_seconds(parameters.get("retry_after"), time.time()))
        if response.status != 200 or body.get("ok") is not True:
            raise DeliveryError(retry_after)


def deliver_one(store, token, chat_id, send=send_telegram, now=None):
    if not token or not chat_id:
        return False  # Missing configuration neither claims nor consumes an attempt.
    clock = time.time if now is None else lambda: now
    job = store.claim(clock())
    if job is None:
        return False
    try:
        send(token, chat_id, job[1], job[2])
    except DeliveryError as error:
        store.finish(job, clock(), False, error.retry_after)
        LOG.warning("Notification deferred or exhausted; no subscriber data logged")
    except Exception:
        # Never log exceptions: transport error strings can contain bot tokens.
        store.finish(job, clock(), False)
        LOG.warning("Notification deferred or exhausted; transport failed")
    else:
        store.finish(job, clock(), True)
    return True


class RateLimiter:
    """Bounded in-memory window; direct socket peers only, plus a global ceiling."""
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.lock = threading.Lock()
        self.peers = {}
        self.global_start = clock()
        self.global_count = 0

    def allow(self, peer):
        with self.lock:
            now = self.clock()
            if now - self.global_start >= 60:
                self.global_start, self.global_count = now, 0
            self.peers = {key: value for key, value in self.peers.items() if now - value[0] < 60}
            start, count = self.peers.get(peer, (now, 0))
            if self.global_count >= 120 or count >= 30 or (peer not in self.peers and len(self.peers) >= 2048):
                return False
            self.global_count += 1
            self.peers[peer] = (start, count + 1)
            return True


class Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 32

    def __init__(self, address, store):
        self.store = store
        self.limiter = RateLimiter()
        self.slots = threading.BoundedSemaphore(32)
        super().__init__(address, Handler)

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(5)
        return connection, address

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()

    def handle_error(self, request, client_address):
        LOG.warning("Request failed; details withheld")


class Handler(BaseHTTPRequestHandler):
    server_version = "Horae"
    sys_version = ""

    def log_message(self, *args):
        pass  # URLs, request lines and subscriber addresses must not enter logs.

    def reply(self, code, body, retry_after=None):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Vary", "Origin")
        if self.headers.get("Origin") in ORIGINS:
            self.send_header("Access-Control-Allow-Origin", self.headers["Origin"])
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Expose-Headers", "Retry-After")
        if retry_after is not None:
            self.send_header("Retry-After", str(retry_after))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path != "/health":
            return self.reply(404, {"error": "Not found"})
        try:
            self.server.store.health()
        except sqlite3.Error:
            return self.reply(503, {"status": "unavailable"})
        self.reply(200, {"status": "ok"})

    def allowed(self):
        if self.path != "/api/waitlist":
            self.reply(404, {"error": "Not found"})
            return False
        if self.headers.get("Origin") not in ORIGINS or len(self.headers.get_all("Origin", [])) != 1:
            self.reply(403, {"error": "Origin not allowed"})
            return False
        return True

    def do_OPTIONS(self):
        if self.allowed():
            if self.headers.get("Access-Control-Request-Method") != "POST" or self.headers.get("Access-Control-Request-Headers", "").lower().strip() not in ("", "content-type"):
                return self.reply(403, {"error": "Preflight not allowed"})
            self.reply(200, {"ok": True})

    def do_POST(self):
        if not self.allowed():
            return
        if not self.server.limiter.allow(self.client_address[0]):
            return self.reply(429, {"error": "Please try again shortly"}, 60)
        if self.headers.get("Transfer-Encoding") or len(self.headers.get_all("Content-Length", [])) != 1:
            return self.reply(400, {"error": "Invalid request length"})
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            return self.reply(400, {"error": "Invalid request length"})
        if not 0 < length <= MAX_BODY:
            return self.reply(413, {"error": "Request too large"})
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
            return self.reply(415, {"error": "JSON required"})
        try:
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError()
            body = json.loads(raw)
            if not isinstance(body, dict) or set(body) - {"email", "website"}:
                raise ValueError()
            trap = body.get("website", "")
            if not isinstance(trap, str) or len(trap) > 256:
                raise ValueError()
            address = normalize_email(body.get("email"))
        except (ValueError, UnicodeError, RecursionError, socket.timeout):
            return self.reply(400, {"error": "Enter a valid email address"})
        if trap:
            return self.reply(200, {"ok": True})
        try:
            self.server.store.signup(address)
        except sqlite3.Error:
            return self.reply(503, {"error": "Unable to save right now. Please retry"}, 30)
        self.reply(200, {"ok": True})


def main():
    os.umask(0o077)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    store = Store(os.environ.get("DATABASE_PATH", "/data/waitlist.sqlite3"))
    stop = threading.Event()
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        LOG.info("Telegram not configured; notifications remain queued")

    def worker():
        while not stop.is_set():
            try:
                worked = deliver_one(store, token, chat_id)
            except Exception:
                LOG.warning("Outbox unavailable; retrying later")
                worked = False
            stop.wait(1 if worked else 5)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    server = Server(("0.0.0.0", int(os.environ.get("PORT", "3000"))), store)

    def shutdown(*_):
        stop.set()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    try:
        server.serve_forever()
    finally:
        stop.set()
        server.server_close()
        thread.join(timeout=20)


if __name__ == "__main__":
    main()
