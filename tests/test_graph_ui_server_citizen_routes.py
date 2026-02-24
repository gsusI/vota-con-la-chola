from __future__ import annotations

from http import HTTPStatus
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest

from scripts import graph_ui_server as g


class TestGraphUiServerCitizenRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(cls._tmpdir.name) / "empty.db"
        db_path.touch()
        handler = g.create_handler(g.AppConfig(db_path=db_path))
        cls._server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls._thread = threading.Thread(target=cls._server.serve_forever, daemon=True)
        cls._thread.start()
        cls._port = int(cls._server.server_port)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._server.shutdown()
        cls._server.server_close()
        cls._thread.join(timeout=5)
        cls._tmpdir.cleanup()

    def _get(self, path: str) -> tuple[int, dict[str, str], bytes]:
        conn = HTTPConnection("127.0.0.1", self._port, timeout=10)
        try:
            conn.request("GET", path)
            response = conn.getresponse()
            body = response.read()
            headers = {k: v for k, v in response.getheaders()}
            return response.status, headers, body
        finally:
            conn.close()

    def test_citizen_path_redirects_to_trailing_slash(self) -> None:
        status, headers, _ = self._get("/citizen")
        self.assertEqual(status, HTTPStatus.FOUND)
        self.assertEqual(headers.get("Location"), "/citizen/")

    def test_citizen_trailing_slash_serves_html(self) -> None:
        status, headers, body = self._get("/citizen/")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertIn("text/html", headers.get("Content-Type", ""))
        self.assertGreater(len(body), 0)


if __name__ == "__main__":
    unittest.main()
