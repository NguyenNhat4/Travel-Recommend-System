"""Monitor lấy lần gọi web / agent từ backend (`/internal/calls`, docs/prd/deployment-plan.md §5)."""
import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock

from monitor import FreshMonitor


class Backend(BaseHTTPRequestHandler):
    status = 200
    seen: list = []

    def do_GET(self):  # noqa: N802
        Backend.seen.append(self.path)
        body = json.dumps({"lastSeq": 7, "events": [{"seq": 7, "source": "agent"}], "summary": [],
                           "catalog": {"products": 5}}).encode()
        self.send_response(Backend.status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body if Backend.status == 200 else b"{}")

    def log_message(self, *args):
        pass


class BackendCallsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), Backend)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "state").mkdir()
        (root / "runs").mkdir()
        self.monitor = FreshMonitor(root / "state", root / "runs")
        Backend.status, Backend.seen = 200, []

    def tearDown(self):
        self.tmp.cleanup()

    def test_proxies_cursor_and_limit_and_names_backend(self):
        with mock.patch.dict(os.environ, {"BACKEND_URL": self.url + "/"}):
            data = self.monitor.backend_calls(after=3, limit=5000)
        self.assertEqual(data["lastSeq"], 7)
        self.assertEqual(data["backend"], self.url)
        self.assertEqual(Backend.seen, ["/internal/calls?after=3&limit=1000"])  # limit bị chặn ở 1000

    def test_old_backend_and_unreachable_backend_give_clear_errors(self):
        Backend.status = 404
        with mock.patch.dict(os.environ, {"BACKEND_URL": self.url}):
            with self.assertRaisesRegex(ValueError, "HTTP 404"):
                self.monitor.backend_calls()
        with mock.patch.dict(os.environ, {"BACKEND_URL": "http://127.0.0.1:9"}):
            with self.assertRaisesRegex(ValueError, "Không gọi được backend"):
                self.monitor.backend_calls()


if __name__ == "__main__":
    unittest.main()
