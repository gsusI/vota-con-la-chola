from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.export_senado_manual_capture_targets import main


class ExportSenadoManualCaptureTargetsTests(unittest.TestCase):
    def _write_packet_json(self, path: Path, *, selected_cohorts: list[str]) -> None:
        payload = {
            "status": "ok",
            "selected_cohorts": [{"cohort": c} for c in selected_cohorts],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def _write_packet_csv(self, path: Path, rows: list[dict[str, str]]) -> None:
        fieldnames = [
            "packet_kind",
            "packet_rank",
            "packet_id",
            "cohort",
            "legislature",
            "tipo_expediente",
            "initiative_id",
            "doc_kind",
            "doc_url",
            "last_http_status",
            "attempts",
            "last_attempt_at",
            "method_hint",
            "is_zero_doc_initiative",
            "cohort_missing_urls",
            "cohort_blocked_403_rate",
        ]
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: row.get(k, "") for k in fieldnames})

    def test_selects_one_per_cohort_then_fills_best_remaining(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            packet_json = root / "packets.json"
            packet_csv = root / "packets.csv"
            out_json = root / "targets.json"
            out_csv = root / "targets.csv"

            self._write_packet_json(packet_json, selected_cohorts=["leg10:tipo610", "leg14:tipo621"])
            self._write_packet_csv(
                packet_csv,
                rows=[
                    {
                        "packet_kind": "cohort",
                        "cohort": "leg10:tipo610",
                        "initiative_id": "senado:10:1",
                        "doc_url": "https://www.senado.es/a",
                        "last_http_status": "403",
                        "attempts": "9",
                        "is_zero_doc_initiative": "0",
                    },
                    {
                        "packet_kind": "cohort",
                        "cohort": "leg14:tipo621",
                        "initiative_id": "senado:14:1",
                        "doc_url": "https://www.senado.es/b",
                        "last_http_status": "403",
                        "attempts": "8",
                        "is_zero_doc_initiative": "1",
                    },
                    {
                        "packet_kind": "cohort",
                        "cohort": "leg10:tipo610",
                        "initiative_id": "senado:10:2",
                        "doc_url": "https://www.senado.es/c",
                        "last_http_status": "500",
                        "attempts": "10",
                        "is_zero_doc_initiative": "1",
                    },
                ],
            )

            rc = main(
                [
                    "--packet-json",
                    str(packet_json),
                    "--packet-csv",
                    str(packet_csv),
                    "--no-include-seed-url",
                    "--max-targets",
                    "3",
                    "--strict",
                    "--out",
                    str(out_json),
                    "--csv-out",
                    str(out_csv),
                ]
            )
            self.assertEqual(rc, 0)

            report = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "ok")
            self.assertEqual(int(report["totals"]["selected_targets_total"]), 3)

            with out_csv.open("r", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 3)
            cohorts = [str(r.get("cohort") or "") for r in rows if str(r.get("target_kind") or "") != "seed"]
            self.assertIn("leg10:tipo610", cohorts)
            self.assertIn("leg14:tipo621", cohorts)

    def test_includes_seed_target_first(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            packet_json = root / "packets.json"
            packet_csv = root / "packets.csv"
            out_json = root / "targets.json"
            out_csv = root / "targets.csv"

            self._write_packet_json(packet_json, selected_cohorts=["leg14:tipo621"])
            self._write_packet_csv(
                packet_csv,
                rows=[
                    {
                        "packet_kind": "cohort",
                        "cohort": "leg14:tipo621",
                        "initiative_id": "senado:14:1",
                        "doc_url": "https://www.senado.es/x",
                        "last_http_status": "403",
                        "attempts": "5",
                        "is_zero_doc_initiative": "1",
                    }
                ],
            )

            rc = main(
                [
                    "--packet-json",
                    str(packet_json),
                    "--packet-csv",
                    str(packet_csv),
                    "--seed-url",
                    "https://www.senado.es/",
                    "--max-targets",
                    "2",
                    "--strict",
                    "--out",
                    str(out_json),
                    "--csv-out",
                    str(out_csv),
                ]
            )
            self.assertEqual(rc, 0)

            with out_csv.open("r", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 2)
            self.assertEqual(str(rows[0].get("target_kind") or ""), "seed")
            self.assertEqual(str(rows[0].get("capture_url") or ""), "https://www.senado.es/")

    def test_strict_fails_when_packet_rows_empty(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            packet_json = root / "packets.json"
            packet_csv = root / "packets.csv"
            out_json = root / "targets.json"
            out_csv = root / "targets.csv"

            self._write_packet_json(packet_json, selected_cohorts=[])
            self._write_packet_csv(packet_csv, rows=[])

            rc = main(
                [
                    "--packet-json",
                    str(packet_json),
                    "--packet-csv",
                    str(packet_csv),
                    "--no-include-seed-url",
                    "--strict",
                    "--out",
                    str(out_json),
                    "--csv-out",
                    str(out_csv),
                ]
            )
            self.assertEqual(rc, 4)
            report = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "degraded")
            reasons = report.get("strict_fail_reasons") or []
            self.assertIn("no_packet_rows", reasons)


if __name__ == "__main__":
    unittest.main()
