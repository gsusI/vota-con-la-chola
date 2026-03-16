from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts import export_senado_manual_capture_pending_targets as target


class ExportSenadoManualCapturePendingTargetsTests(unittest.TestCase):
    def _write_progress_json(self, path: Path) -> None:
        payload = {
            "status": "degraded",
            "checks": {"has_targets": True, "covered_targets_min_met": True, "usable_targets_min_met": False},
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _write_progress_csv(self, path: Path, rows: list[dict[str, str]]) -> None:
        fieldnames = [
            "target_rank",
            "target_id",
            "target_kind",
            "cohort",
            "initiative_id",
            "capture_url",
            "reason",
            "suggested_label",
            "suggested_command",
            "matched",
            "match_strategy",
            "matched_meta_file",
            "matched_final_url",
            "matched_ended_at",
            "matched_access_denied",
            "matched_cookies_domain_total",
            "matched_usable_capture",
        ]
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: row.get(k, "") for k in fieldnames})

    def test_exports_pending_queue_and_fails_strict_when_not_empty(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            progress_json = root / "progress.json"
            progress_csv = root / "progress.csv"
            out_json = root / "pending.json"
            out_csv = root / "pending.csv"
            out_commands = root / "pending.sh"

            self._write_progress_json(progress_json)
            self._write_progress_csv(
                progress_csv,
                rows=[
                    {
                        "target_rank": "1",
                        "target_id": "t1",
                        "cohort": "seed",
                        "capture_url": "https://www.senado.es/",
                        "suggested_command": "cmd_seed",
                        "matched": "1",
                        "matched_access_denied": "1",
                        "matched_cookies_domain_total": "0",
                        "matched_usable_capture": "0",
                    },
                    {
                        "target_rank": "2",
                        "target_id": "t2",
                        "cohort": "leg14",
                        "capture_url": "https://www.senado.es/x",
                        "suggested_label": "senado_cookie_refresh_ai_ops_299_02_leg14_tipo610",
                        "suggested_command": "",
                        "matched": "0",
                        "matched_access_denied": "0",
                        "matched_cookies_domain_total": "0",
                        "matched_usable_capture": "0",
                    },
                    {
                        "target_rank": "3",
                        "target_id": "t3",
                        "cohort": "leg10",
                        "capture_url": "https://www.senado.es/y",
                        "suggested_command": "cmd_y",
                        "matched": "1",
                        "matched_access_denied": "0",
                        "matched_cookies_domain_total": "3",
                        "matched_usable_capture": "1",
                    },
                ],
            )

            rc = target.main(
                [
                    "--progress-json",
                    str(progress_json),
                    "--progress-csv",
                    str(progress_csv),
                    "--out",
                    str(out_json),
                    "--csv-out",
                    str(out_csv),
                    "--commands-out",
                    str(out_commands),
                    "--strict",
                ]
            )
            self.assertEqual(rc, target.STRICT_FAIL_EXIT)
            report = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "degraded")
            self.assertEqual(int(report["totals"]["pending_targets_total"]), 2)
            self.assertEqual(int(report["totals"]["pending_access_denied_total"]), 1)
            self.assertEqual(int(report["totals"]["pending_commands_total"]), 2)
            self.assertEqual(int(report["totals"]["pending_commands_fallback_total"]), 1)
            self.assertIn("pending_targets_remaining", report["strict_fail_reasons"])

            with out_csv.open("r", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 2)
            self.assertEqual(str(rows[0].get("pending_reason") or ""), "unmatched_target")
            self.assertEqual(str(rows[1].get("pending_reason") or ""), "matched_access_denied")

            commands = out_commands.read_text(encoding="utf-8")
            self.assertIn("cmd_seed", commands)
            self.assertIn("manual_capture_playwright.py", commands)
            self.assertIn("https://www.senado.es/x", commands)

    def test_ok_when_pending_queue_empty(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            progress_json = root / "progress.json"
            progress_csv = root / "progress.csv"
            out_json = root / "pending.json"
            out_csv = root / "pending.csv"
            out_commands = root / "pending.sh"

            self._write_progress_json(progress_json)
            self._write_progress_csv(
                progress_csv,
                rows=[
                    {
                        "target_rank": "1",
                        "target_id": "t1",
                        "cohort": "seed",
                        "capture_url": "https://www.senado.es/",
                        "suggested_command": "cmd_seed",
                        "matched": "1",
                        "matched_access_denied": "0",
                        "matched_cookies_domain_total": "2",
                        "matched_usable_capture": "1",
                    }
                ],
            )

            rc = target.main(
                [
                    "--progress-json",
                    str(progress_json),
                    "--progress-csv",
                    str(progress_csv),
                    "--out",
                    str(out_json),
                    "--csv-out",
                    str(out_csv),
                    "--commands-out",
                    str(out_commands),
                    "--strict",
                ]
            )
            self.assertEqual(rc, 0)
            report = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "ok")
            self.assertEqual(int(report["totals"]["pending_targets_total"]), 0)

    def test_failed_when_progress_csv_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            progress_json = root / "progress.json"
            out_json = root / "pending.json"
            out_csv = root / "pending.csv"
            out_commands = root / "pending.sh"

            self._write_progress_json(progress_json)

            rc = target.main(
                [
                    "--progress-json",
                    str(progress_json),
                    "--progress-csv",
                    str(root / "missing.csv"),
                    "--out",
                    str(out_json),
                    "--csv-out",
                    str(out_csv),
                    "--commands-out",
                    str(out_commands),
                ]
            )
            self.assertEqual(rc, 3)
            report = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "failed")
            self.assertEqual(report.get("error"), "progress_csv_not_found")


if __name__ == "__main__":
    unittest.main()
