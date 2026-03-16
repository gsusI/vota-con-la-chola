from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import report_senado_manual_capture_validity as target


class ReportSenadoManualCaptureValidityTests(unittest.TestCase):
    def _write_capture(
        self,
        root: Path,
        stem: str,
        *,
        title: str,
        html: str,
        cookies: list[dict],
    ) -> Path:
        meta_path = root / f"{stem}.meta.json"
        html_path = root / f"{stem}.html"
        cookie_path = root / f"{stem}.cookies.json"

        meta = {
            "result": {
                "status": "captured",
                "title": title,
                "final_url": "https://www.senado.es/",
                "html_len": len(html),
            }
        }
        meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        html_path.write_text(html, encoding="utf-8")
        cookie_path.write_text(json.dumps(cookies, ensure_ascii=False), encoding="utf-8")
        return meta_path

    def test_degraded_when_access_denied_or_no_domain_cookies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_capture(
                root,
                "capture1",
                title="Access Denied",
                html="<html><title>Access Denied</title><body>Access Denied</body></html>",
                cookies=[],
            )
            report = target.build_report(
                captures_glob=str(root / "*.meta.json"),
                cookie_domain_contains="senado.es",
                min_captures=1,
            )
            self.assertEqual(report["status"], "degraded")
            self.assertEqual(report["totals"]["captures_total"], 1)
            self.assertEqual(report["totals"]["usable_captures_total"], 0)
            self.assertIn("no_usable_capture", report["strict_fail_reasons"])

    def test_ok_when_has_non_deny_capture_with_domain_cookie(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_capture(
                root,
                "capture_ok",
                title="Senado",
                html="<html><title>Senado</title><body>ok</body></html>",
                cookies=[{"name": "foo", "domain": "www.senado.es", "expires": 0}],
            )
            report = target.build_report(
                captures_glob=str(root / "*.meta.json"),
                cookie_domain_contains="senado.es",
                min_captures=1,
            )
            self.assertEqual(report["status"], "ok")
            self.assertEqual(report["totals"]["usable_captures_total"], 1)
            self.assertEqual(report["strict_fail_reasons"], [])

    def test_main_strict_rc_4_on_degraded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_capture(
                root,
                "capture_bad",
                title="Access Denied",
                html="<html>Access Denied</html>",
                cookies=[],
            )
            out_path = root / "out.json"
            rc = target.main(
                [
                    "--captures-glob",
                    str(root / "*.meta.json"),
                    "--cookie-domain-contains",
                    "senado.es",
                    "--strict",
                    "--out",
                    str(out_path),
                ]
            )
            self.assertEqual(rc, 4)
            saved = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["status"], "degraded")


if __name__ == "__main__":
    unittest.main()
