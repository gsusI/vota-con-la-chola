from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_citizen_mobile_performance_budget import main


class TestReportCitizenMobilePerformanceBudget(unittest.TestCase):
    def _write_html_with_markers(self, path: Path, *, include_markers: bool) -> None:
        markers = "\n".join(
            [
                "const SEARCH_INPUT_DEBOUNCE_MS = 120;",
                "const RENDER_COMPARE_SCHEDULE = \"raf\";",
                "const MOBILE_LATENCY_OBS_VERSION = \"v1\";",
                "function scheduleRenderCompare() {}",
                "function markInputLatencySampleStart() {}",
                "function commitInputLatencySample() {}",
                'qs("#concernSearch")?.addEventListener("input", onConcernSearchInputRaw);',
                'qs("#topicSearch")?.addEventListener("input", onTopicSearchInputRaw);',
            ]
        )
        body = markers if include_markers else "const x = 1;"
        path.write_text(body + "\n", encoding="utf-8")

    def test_main_passes_when_within_budget_and_markers_present(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            ui_html = td_path / "index.html"
            a1 = td_path / "a.js"
            a2 = td_path / "b.js"
            snapshot = td_path / "citizen.json"
            out = td_path / "report.json"

            self._write_html_with_markers(ui_html, include_markers=True)
            a1.write_text("console.log('a');\n", encoding="utf-8")
            a2.write_text("console.log('b');\n", encoding="utf-8")
            snapshot.write_text('{"ok":true}\n', encoding="utf-8")

            rc = main(
                [
                    "--ui-html",
                    str(ui_html),
                    "--ui-assets",
                    f"{a1},{a2}",
                    "--snapshot",
                    str(snapshot),
                    "--max-ui-html-bytes",
                    "1000",
                    "--max-ui-assets-total-bytes",
                    "1000",
                    "--max-snapshot-bytes",
                    "1000",
                    "--strict",
                    "--out",
                    str(out),
                ]
            )
            self.assertEqual(rc, 0)

            got = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(got["status"], "ok")
            self.assertTrue(got["checks"]["interaction_markers_present"])
            self.assertEqual(got["failure_reasons"], [])

    def test_main_strict_fails_when_markers_missing_or_budget_exceeded(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            ui_html = td_path / "index.html"
            a1 = td_path / "a.js"
            snapshot = td_path / "citizen.json"
            out = td_path / "report.json"

            self._write_html_with_markers(ui_html, include_markers=False)
            a1.write_text("x" * 400 + "\n", encoding="utf-8")
            snapshot.write_text("{}\n", encoding="utf-8")

            rc = main(
                [
                    "--ui-html",
                    str(ui_html),
                    "--ui-assets",
                    str(a1),
                    "--snapshot",
                    str(snapshot),
                    "--max-ui-html-bytes",
                    "10",
                    "--max-ui-assets-total-bytes",
                    "100",
                    "--max-snapshot-bytes",
                    "1000",
                    "--strict",
                    "--out",
                    str(out),
                ]
            )
            self.assertEqual(rc, 4)

            got = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(got["status"], "failed")
            self.assertIn("ui_html_over_budget", got["failure_reasons"])
            self.assertIn("ui_assets_total_over_budget", got["failure_reasons"])
            self.assertIn("interaction_markers_missing", got["failure_reasons"])


if __name__ == "__main__":
    unittest.main()
