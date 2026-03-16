from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts import report_programas_support_precision_audit as target


class TestReportProgramasSupportPrecisionAudit(unittest.TestCase):
    def _write_sample(self, rows: list[dict[str, str]]) -> Path:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
        path = Path(tmp.name)
        tmp.close()
        with path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "sample_id",
                    "party_name",
                    "source_url",
                    "evidence_id",
                    "excerpt",
                    "manual_label",
                    "manual_note",
                ],
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
        return path

    def test_build_report_passes_threshold(self) -> None:
        sample = self._write_sample(
            [
                {
                    "sample_id": "S001",
                    "party_name": "BNG",
                    "source_url": "https://bng/1",
                    "evidence_id": "1",
                    "excerpt": "x",
                    "manual_label": "true_positive",
                    "manual_note": "",
                },
                {
                    "sample_id": "S002",
                    "party_name": "VOX",
                    "source_url": "https://vox/1",
                    "evidence_id": "2",
                    "excerpt": "x",
                    "manual_label": "false_positive",
                    "manual_note": "",
                },
                {
                    "sample_id": "S003",
                    "party_name": "PP",
                    "source_url": "https://pp/1",
                    "evidence_id": "3",
                    "excerpt": "x",
                    "manual_label": "true_positive",
                    "manual_note": "",
                },
            ]
        )
        try:
            report = target.build_report(
                sample_path=sample,
                min_precision=0.66,
                min_reviewed=3,
                min_party_precision=0.0,
                required_parties=["BNG", "VOX", "PP"],
            )
            self.assertEqual(report["status"], "ok")
            self.assertEqual(int(report["reviewed_total"]), 3)
            self.assertEqual(int(report["false_positive"]), 1)
            self.assertEqual(report["false_positive_evidence_ids"], [2])
        finally:
            sample.unlink(missing_ok=True)

    def test_build_report_flags_missing_party_and_invalid_labels(self) -> None:
        sample = self._write_sample(
            [
                {
                    "sample_id": "S001",
                    "party_name": "BNG",
                    "source_url": "https://bng/1",
                    "evidence_id": "1",
                    "excerpt": "x",
                    "manual_label": "true_positive",
                    "manual_note": "",
                },
                {
                    "sample_id": "S002",
                    "party_name": "VOX",
                    "source_url": "https://vox/1",
                    "evidence_id": "2",
                    "excerpt": "x",
                    "manual_label": "invalid_label",
                    "manual_note": "",
                },
                {
                    "sample_id": "S003",
                    "party_name": "VOX",
                    "source_url": "https://vox/2",
                    "evidence_id": "3",
                    "excerpt": "x",
                    "manual_label": "",
                    "manual_note": "",
                },
            ]
        )
        try:
            report = target.build_report(
                sample_path=sample,
                min_precision=0.90,
                min_reviewed=2,
                min_party_precision=0.0,
                required_parties=["BNG", "VOX", "PP"],
            )
            self.assertEqual(report["status"], "degraded")
            self.assertEqual(int(report["invalid_label_rows"]), 1)
            self.assertEqual(report["missing_required_parties"], ["VOX", "PP"])
            self.assertIn("invalid_manual_labels", report["strict_fail_reasons"])
            self.assertIn("missing_required_parties", report["strict_fail_reasons"])
        finally:
            sample.unlink(missing_ok=True)

    def test_main_strict_returns_4_when_degraded(self) -> None:
        sample = self._write_sample(
            [
                {
                    "sample_id": "S001",
                    "party_name": "BNG",
                    "source_url": "https://bng/1",
                    "evidence_id": "1",
                    "excerpt": "x",
                    "manual_label": "false_positive",
                    "manual_note": "",
                }
            ]
        )
        out_path = Path(tempfile.NamedTemporaryFile(delete=False, suffix=".json").name)
        try:
            rc = target.main(
                [
                    "--in",
                    str(sample),
                    "--out",
                    str(out_path),
                    "--strict",
                    "--min-reviewed",
                    "1",
                    "--required-parties",
                    "BNG",
                ]
            )
            self.assertEqual(rc, 4)
            payload = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "degraded")
        finally:
            sample.unlink(missing_ok=True)
            out_path.unlink(missing_ok=True)

    def test_build_report_flags_required_party_precision_below_threshold(self) -> None:
        sample = self._write_sample(
            [
                {
                    "sample_id": "S001",
                    "party_name": "BNG",
                    "source_url": "https://bng/1",
                    "evidence_id": "1",
                    "excerpt": "x",
                    "manual_label": "true_positive",
                    "manual_note": "",
                },
                {
                    "sample_id": "S002",
                    "party_name": "BNG",
                    "source_url": "https://bng/2",
                    "evidence_id": "2",
                    "excerpt": "x",
                    "manual_label": "false_positive",
                    "manual_note": "",
                },
                {
                    "sample_id": "S003",
                    "party_name": "VOX",
                    "source_url": "https://vox/1",
                    "evidence_id": "3",
                    "excerpt": "x",
                    "manual_label": "true_positive",
                    "manual_note": "",
                },
            ]
        )
        try:
            report = target.build_report(
                sample_path=sample,
                min_precision=0.60,
                min_reviewed=3,
                min_party_precision=0.75,
                required_parties=["BNG", "VOX"],
            )
            self.assertEqual(report["status"], "degraded")
            self.assertEqual(report["checks"]["required_parties_min_precision"], False)
            self.assertIn("required_party_precision_below_threshold", report["strict_fail_reasons"])
            self.assertEqual(report["below_min_party_precision"], [{"party_name": "BNG", "precision": 0.5, "reviewed_total": 2}])
        finally:
            sample.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
