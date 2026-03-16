from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from scripts import report_senado_cookie_lever_status as target


class ReportSenadoCookieLeverStatusTests(unittest.TestCase):
    def _write_cookie_file(self, rows: list[dict], *, age_hours: float = 0.0) -> Path:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".cookies.json")
        path = Path(tmp.name)
        tmp.close()
        path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        if age_hours > 0:
            now = time.time()
            old_ts = now - (age_hours * 3600.0)
            os.utime(path, (old_ts, old_ts))
        return path

    def test_degraded_when_stale_session_only(self) -> None:
        cookie_file = self._write_cookie_file(
            [
                {"name": "JSESSIONID", "domain": "www.senado.es", "path": "/", "expires": -1},
                {"name": "TS0183a7e2", "domain": "www.senado.es", "path": "/", "expires": -1},
            ],
            age_hours=48.0,
        )
        try:
            report = target.build_report(
                cookie_file=cookie_file,
                domain_contains="senado.es",
                max_age_hours=24.0,
                min_domain_cookies=1,
                min_unexpired_persistent_cookies=1,
            )
            self.assertEqual(report["status"], "degraded")
            self.assertTrue(report["no_new_lever"])
            self.assertFalse(report["checks"]["file_age_within_threshold"])
            self.assertFalse(report["checks"]["has_unexpired_persistent_cookies"])
            self.assertIn("cookie_file_stale", report["strict_fail_reasons"])
            self.assertIn("no_unexpired_persistent_cookies", report["strict_fail_reasons"])
        finally:
            cookie_file.unlink(missing_ok=True)

    def test_ok_with_fresh_unexpired_persistent_cookie(self) -> None:
        expires = int(time.time()) + 3600
        cookie_file = self._write_cookie_file(
            [
                {
                    "name": "TS0183a7e2",
                    "domain": "www.senado.es",
                    "path": "/",
                    "expires": expires,
                    "secure": True,
                    "httpOnly": True,
                }
            ]
        )
        try:
            report = target.build_report(
                cookie_file=cookie_file,
                domain_contains="senado.es",
                max_age_hours=24.0,
                min_domain_cookies=1,
                min_unexpired_persistent_cookies=1,
            )
            self.assertEqual(report["status"], "ok")
            self.assertFalse(report["no_new_lever"])
            self.assertTrue(report["checks"]["file_age_within_threshold"])
            self.assertTrue(report["checks"]["has_unexpired_persistent_cookies"])
        finally:
            cookie_file.unlink(missing_ok=True)

    def test_main_strict_returns_4_for_degraded(self) -> None:
        cookie_file = self._write_cookie_file(
            [{"name": "JSESSIONID", "domain": "www.senado.es", "path": "/", "expires": -1}],
            age_hours=30.0,
        )
        out_path = Path(tempfile.NamedTemporaryFile(delete=False, suffix=".json").name)
        try:
            rc = target.main(
                [
                    "--cookie-file",
                    str(cookie_file),
                    "--max-age-hours",
                    "24",
                    "--strict",
                    "--out",
                    str(out_path),
                ]
            )
            self.assertEqual(rc, 4)
            saved = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["status"], "degraded")
        finally:
            cookie_file.unlink(missing_ok=True)
            out_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
