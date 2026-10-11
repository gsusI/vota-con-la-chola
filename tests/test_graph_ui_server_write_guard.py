from __future__ import annotations

from http import HTTPStatus
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
import json
import sys
import tempfile
import threading
import unittest
from unittest import mock

from scripts import graph_ui_server as g

ENDPOINT = "/api/topics/reviews/decision"


class TestGraphUiServerWriteGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(cls._tmpdir.name) / "empty.db"
        db_path.touch()
        cls._server = ThreadingHTTPServer(("127.0.0.1", 0), g.create_handler(g.AppConfig(db_path=db_path)))
        cls._thread = threading.Thread(target=cls._server.serve_forever, daemon=True)
        cls._thread.start()
        cls._host = f"127.0.0.1:{cls._server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls._server.shutdown()
        cls._server.server_close()
        cls._thread.join(timeout=5)
        cls._tmpdir.cleanup()

    def _post(self, headers: dict[str, str]) -> int:
        conn = HTTPConnection(*self._host.split(":"), timeout=10)
        try:
            body = json.dumps({"evidence_ids": [1], "dry_run": True})
            conn.request("POST", ENDPOINT, body=body, headers=headers)
            response = conn.getresponse()
            response.read()
            return response.status
        finally:
            conn.close()

    def test_default_host_is_loopback(self) -> None:
        with mock.patch.object(sys, "argv", ["graph_ui_server.py"]):
            self.assertEqual(g.parse_args().host, "127.0.0.1")

    def test_rejects_non_json_simple_request(self) -> None:
        # text/plain is a CORS "simple request": a foreign page could send it without preflight.
        self.assertEqual(self._post({"Content-Type": "text/plain"}), HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
        self.assertEqual(self._post({}), HTTPStatus.UNSUPPORTED_MEDIA_TYPE)

    def test_rejects_foreign_origin(self) -> None:
        status = self._post({"Content-Type": "application/json", "Origin": "https://evil.example"})
        self.assertEqual(status, HTTPStatus.FORBIDDEN)

    def test_rejects_cross_site_fetch_metadata(self) -> None:
        status = self._post({"Content-Type": "application/json", "Sec-Fetch-Site": "cross-site"})
        self.assertEqual(status, HTTPStatus.FORBIDDEN)

    def test_same_origin_json_reaches_handler(self) -> None:
        status = self._post(
            {
                "Content-Type": "application/json; charset=utf-8",
                "Origin": f"http://{self._host}",
                "Sec-Fetch-Site": "same-origin",
            }
        )
        self.assertNotIn(status, {HTTPStatus.FORBIDDEN, HTTPStatus.UNSUPPORTED_MEDIA_TYPE})
        # Non-browser clients (curl, scripts) send neither Origin nor Sec-Fetch-Site.
        self.assertNotIn(self._post({"Content-Type": "application/json"}), {HTTPStatus.FORBIDDEN, HTTPStatus.UNSUPPORTED_MEDIA_TYPE})


if __name__ == "__main__":
    unittest.main()
