from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.check_next_export_notfound_payloads import find_notfound_payloads


class TestCheckNextExportNotfoundPayloads(unittest.TestCase):
    def test_finds_next_error_markers_in_exported_html(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            ok_path = root / "vote-explainer" / "good" / "index.html"
            bad_path = root / "vote-explainer" / "bad" / "index.html"
            ok_path.parent.mkdir(parents=True)
            bad_path.parent.mkdir(parents=True)

            ok_path.write_text('<html lang="es"><main>Vote explainer MVP</main></html>', encoding="utf-8")
            bad_path.write_text('<html id="__next_error__"><script>NEXT_HTTP_ERROR_FALLBACK;404</script></html>', encoding="utf-8")

            self.assertEqual(find_notfound_payloads([root]), [bad_path])

    def test_ignores_regular_content_that_mentions_404(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            html_path = root / "index.html"
            html_path.write_text("<html><body>HTTP 404 is discussed as text.</body></html>", encoding="utf-8")

            self.assertEqual(find_notfound_payloads([root]), [])


if __name__ == "__main__":
    unittest.main()
