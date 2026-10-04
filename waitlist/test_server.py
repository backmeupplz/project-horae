import concurrent.futures
import http.client
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
import urllib.error

import server


class StoreFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "waitlist.sqlite3"
        self.store = server.Store(self.path)

    def row(self):
        with self.store.connect() as db:
            db.row_factory = sqlite3.Row
            return dict(db.execute("SELECT * FROM outbox").fetchone())


class StoreTests(StoreFixture):
    def test_new_duplicate_and_restart(self):
        address = server.normalize_email("  A.B+tag@EXAMPLE.COM  ")
        self.assertEqual(address, "a.b+tag@example.com")
        self.assertTrue(self.store.signup(address))
        self.assertFalse(self.store.signup(address))
        restarted = server.Store(self.path)
        self.assertFalse(restarted.signup(address))
        with restarted.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM signups").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT count(*) FROM outbox").fetchone()[0], 1)
            self.assertIn("+00:00", db.execute("SELECT created_at FROM signups").fetchone()[0])

    def test_concurrent_dedup(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(lambda _: self.store.signup("same@example.com"), range(32)))
        self.assertEqual(sum(results), 1)
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM outbox").fetchone()[0], 1)

    def test_outbox_failure_rolls_back_signup(self):
        with self.store.connect() as db:
            db.execute("CREATE TRIGGER fail_outbox BEFORE INSERT ON outbox BEGIN SELECT RAISE(ABORT, 'test failure'); END")
        with self.assertRaises(sqlite3.Error):
            self.store.signup("rollback@example.com")
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM signups").fetchone()[0], 0)

    def test_invalid_inputs(self):
        for value in [None, 1, [], "", "a", "a@b", "a@@b.com", "a..b@c.com", ".a@c.com", "a.@c.com", "a b@c.com", "a@-b.com", "a@b_.com", "a@b..com", "a\n@b.com", "a@b.com\n", "é@b.com", "a" * 65 + "@b.com", "a@" + "b" * 64 + ".com", "x" * 321]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                server.normalize_email(value)

    def test_missing_bot_never_consumes_attempts(self):
        self.store.signup("saved@example.com")
        send = Mock()
        for token, chat in [("", ""), ("token", ""), ("", "chat")]:
            self.assertFalse(server.deliver_one(self.store, token, chat, send, now=100))
        send.assert_not_called()
        self.assertEqual(self.row()["attempts"], 0)
        self.assertEqual(self.row()["lease_until"], 0)

    def test_delivery_once_after_duplicate_and_restart(self):
        self.store.signup("saved@example.com")
        send = Mock()
        self.assertTrue(server.deliver_one(self.store, "fake", "fake", send, now=100))
        self.store.signup("saved@example.com")
        self.assertFalse(server.deliver_one(server.Store(self.path), "fake", "fake", send, now=200))
        self.assertEqual(send.call_count, 1)
        self.assertIsNotNone(self.row()["delivered_at"])

    def test_retry_after_backoff_and_exhaustion(self):
        self.store.signup("saved@example.com")
        send = Mock(side_effect=server.DeliveryError(180))
        now = 100
        for attempt in range(1, server.MAX_ATTEMPTS + 1):
            self.assertTrue(server.deliver_one(self.store, "fake", "fake", send, now=now))
            row = self.row()
            self.assertEqual(row["attempts"], attempt)
            self.assertGreaterEqual(row["next_attempt"], now + 180)
            self.assertFalse(server.deliver_one(server.Store(self.path), "fake", "fake", send, now=now + 1))
            now = row["next_attempt"]
        self.assertIsNotNone(self.row()["failed_at"])
        self.assertFalse(server.deliver_one(self.store, "fake", "fake", send, now=now + 10000))
        self.assertEqual(send.call_count, server.MAX_ATTEMPTS)

    def test_crashed_claim_recovers_and_stale_owner_cannot_finish(self):
        self.store.signup("saved@example.com")
        old = self.store.claim(100)
        restarted = server.Store(self.path)
        self.assertIsNone(restarted.claim(101))
        new = restarted.claim(100 + server.LEASE_SECONDS)
        self.assertIsNotNone(new)
        self.store.finish(old, 221, True)
        self.assertIsNone(self.row()["delivered_at"])
        restarted.finish(new, 222, True)
        self.assertIsNotNone(self.row()["delivered_at"])

    def test_final_crashed_claim_exhausts(self):
        self.store.signup("saved@example.com")
        with self.store.connect() as db:
            db.execute("UPDATE outbox SET attempts=?", (server.MAX_ATTEMPTS - 1,))
        self.store.claim(100)
        self.assertIsNone(server.Store(self.path).claim(221))
        self.assertIsNotNone(self.row()["failed_at"])

    def test_retry_after_is_measured_after_network_call(self):
        self.store.signup("saved@example.com")
        send = Mock(side_effect=server.DeliveryError(180))
        # Do not replace the shared time module also used by Python 3.12 logging.
        with patch("server.time", Mock(time=Mock(side_effect=[100, 115]))):
            server.deliver_one(self.store, "fake", "fake", send)
        self.assertEqual(self.row()["next_attempt"], 295)

    def check_shared_retry_after(self, reopen):
        self.store.signup("first@example.com")
        self.store.signup("second@example.com")
        send = Mock(side_effect=server.DeliveryError(180))
        # Keep logging's clock independent of the two application timestamps.
        with patch("server.time", Mock(time=Mock(side_effect=[100, 115]))):
            self.assertTrue(server.deliver_one(self.store, "fake", "fake", send))
        if reopen:
            self.store = server.Store(self.path)
        with self.store.connect() as db:
            before = db.execute("SELECT * FROM outbox ORDER BY signup_id").fetchall()
        for now in [116, 280, 294.999]:
            self.assertFalse(server.deliver_one(self.store, "fake", "fake", send, now=now))
        self.assertEqual(send.call_count, 1)
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT * FROM outbox ORDER BY signup_id").fetchall(), before)
            self.assertEqual(db.execute("SELECT attempts FROM outbox ORDER BY signup_id").fetchall(), [(1,), (0,)])
        send.side_effect = None
        self.assertTrue(server.deliver_one(self.store, "fake", "fake", send, now=295))
        self.assertTrue(server.deliver_one(self.store, "fake", "fake", send, now=296))
        self.assertEqual([call.args[2] for call in send.call_args_list],
                         ["first@example.com", "first@example.com", "second@example.com"])
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT attempts, delivered_at IS NOT NULL FROM outbox ORDER BY signup_id").fetchall(), [(2, 1), (1, 1)])

    def test_retry_after_blocks_all_pending_signups(self):
        self.check_shared_retry_after(reopen=False)

    def test_retry_after_blocks_all_pending_signups_after_restart(self):
        self.check_shared_retry_after(reopen=True)

    def test_retry_and_signup_failures_do_not_leak_logs(self):
        self.store.signup("private@example.com")
        send = Mock(side_effect=RuntimeError("SECRET-TOKEN private@example.com"))
        with self.assertLogs("waitlist", level="WARNING") as logs:
            server.deliver_one(self.store, "fake", "fake", send, now=100)
        self.assertNotIn("private@example.com", str(logs.output))
        self.assertNotIn("SECRET-TOKEN", str(logs.output))
        self.assertEqual(self.row()["attempts"], 1)
        self.assertIsNone(self.row()["delivered_at"])

    def test_parallel_claims_only_one_owner(self):
        self.store.signup("saved@example.com")
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            jobs = list(pool.map(lambda _: self.store.claim(100), range(8)))
        self.assertEqual(sum(job is not None for job in jobs), 1)


class APITests(StoreFixture):
    def setUp(self):
        super().setUp()
        self.http = server.Server(("127.0.0.1", 0), self.store)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close_http)

    def close_http(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join()

    def request(self, body=None, origin="https://projecthorae.com", method="POST", path="/api/waitlist", headers=None):
        connection = http.client.HTTPConnection(*self.http.server_address, timeout=3)
        request_headers = {"Content-Type": "application/json"}
        if origin is not None:
            request_headers["Origin"] = origin
        request_headers.update(headers or {})
        data = json.dumps(body) if body is not None else None
        try:
            connection.request(method, path, data, request_headers)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), json.loads(response.read())
        finally:
            connection.close()

    def test_http_new_duplicate_honeypot_and_no_reads(self):
        first = self.request({"email": "New+one@Example.COM"})
        duplicate = self.request({"email": "new+one@example.com"})
        self.assertEqual(first[0], duplicate[0])
        self.assertEqual(first[2], duplicate[2])
        self.assertEqual(first[0], 200)
        self.assertEqual(first[1]["Access-Control-Allow-Origin"], "https://projecthorae.com")
        self.assertEqual(self.request({"email": "trap@example.com", "website": "bot"})[0], 200)
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM signups").fetchone()[0], 1)
        for path in ["/api/waitlist", "/export", "/data/waitlist.sqlite3"]:
            self.assertEqual(self.request(method="GET", path=path)[0], 404)
        self.assertEqual(self.request(method="GET", path="/health", origin=None)[0], 200)

    def test_http_db_failure(self):
        with patch.object(self.store, "signup", side_effect=sqlite3.OperationalError("private failure")):
            status, headers, body = self.request({"email": "good@example.com"})
        self.assertEqual(status, 503)
        self.assertEqual(headers["Retry-After"], "30")
        self.assertNotIn("private", json.dumps(body))

    def test_http_validation_cors_and_preflight(self):
        for origin in [None, "null", "https://evil.example", "https://projecthorae.com.evil.example", "http://projecthorae.com"]:
            response = self.request({"email": "valid@example.com"}, origin=origin)
            self.assertEqual(response[0], 403)
            self.assertNotIn("Access-Control-Allow-Origin", response[1])
        for body in [{"email": "bad"}, [], {"email": "valid@example.com", "website": []}, {"email": "valid@example.com", "extra": 1}]:
            self.assertEqual(self.request(body)[0], 400)
        self.assertEqual(self.request({"email": "x" * 3000})[0], 413)
        self.assertEqual(self.request({"email": "valid@example.com"}, headers={"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.request(method="OPTIONS", origin="https://www.projecthorae.com", headers={"Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})[0], 200)
        self.assertEqual(self.request(method="OPTIONS", headers={"Access-Control-Request-Method": "DELETE"})[0], 403)

    def test_forwarded_ip_does_not_bypass_limit(self):
        for i in range(30):
            self.assertEqual(self.request({"email": "same@example.com"}, headers={"X-Forwarded-For": f"192.0.2.{i}"})[0], 200)
        result = self.request({"email": "same@example.com"}, headers={"X-Forwarded-For": "198.51.100.1"})
        self.assertEqual(result[0], 429)
        self.assertEqual(result[1]["Retry-After"], "60")


class TelegramTests(unittest.TestCase):
    @patch("server.urllib.request.build_opener")
    def test_plain_payload_and_success(self, build):
        response = Mock(status=200, headers={})
        response.read.return_value = b'{"ok":true}'
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        build.return_value.open.return_value = response
        server.send_telegram("test-token", "123", "a+b@example.com", "2026-10-04T00:00:00+00:00")
        request = build.return_value.open.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(set(payload), {"chat_id", "text"})
        self.assertIn("a+b@example.com", payload["text"])
        self.assertIn("2026-10-04", payload["text"])
        self.assertEqual(build.return_value.open.call_args.kwargs["timeout"], 15)

    @patch("server.urllib.request.build_opener")
    def test_429_honors_body_and_header(self, build):
        build.return_value.open.side_effect = urllib.error.HTTPError("https://example.invalid", 429, "limited", {"Retry-After": "120"}, io.BytesIO(b'{"ok":false,"parameters":{"retry_after":240}}'))
        with self.assertRaises(server.DeliveryError) as raised:
            server.send_telegram("fake", "fake", "a@example.com", "now")
        self.assertEqual(raised.exception.retry_after, 240)

    def test_retry_dates_and_invalid_values(self):
        self.assertEqual(server.retry_seconds("Thu, 01 Jan 1970 00:02:00 GMT", 60), 60)
        for value in [None, "bad", "NaN", "inf", -10]:
            self.assertEqual(server.retry_seconds(value, 0), 0)

    def test_rate_limiter_window_and_bound(self):
        now = [0]
        limiter = server.RateLimiter(lambda: now[0])
        for _ in range(30):
            self.assertTrue(limiter.allow("peer"))
        self.assertFalse(limiter.allow("peer"))
        now[0] = 60
        self.assertTrue(limiter.allow("peer"))
        for i in range(119):
            self.assertTrue(limiter.allow(str(i)))
        self.assertFalse(limiter.allow("other"))
        self.assertLessEqual(len(limiter.peers), 2048)


if __name__ == "__main__":
    unittest.main()
