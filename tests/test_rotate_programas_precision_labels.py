from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts import rotate_programas_precision_labels as target


class TestRotateProgramasPrecisionLabels(unittest.TestCase):
    def _write_csv(self, rows: list[dict[str, str]]) -> Path:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
        path = Path(tmp.name)
        tmp.close()
        fieldnames = [
            "sample_id",
            "party_name",
            "source_url",
            "evidence_id",
            "excerpt",
            "manual_label",
            "manual_note",
        ]
        with path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: str(row.get(k) or "") for k in fieldnames})
        return path

    def test_carry_forward_and_unlabeled_counts(self) -> None:
        sample = self._write_csv(
            [
                {"sample_id": "S001", "party_name": "BNG", "evidence_id": "1", "manual_label": "", "manual_note": ""},
                {"sample_id": "S002", "party_name": "VOX", "evidence_id": "2", "manual_label": "", "manual_note": ""},
                {"sample_id": "S003", "party_name": "PP", "evidence_id": "3", "manual_label": "true_positive", "manual_note": "manual"},
            ]
        )
        labels = self._write_csv(
            [
                {"sample_id": "A001", "party_name": "BNG", "evidence_id": "1", "manual_label": "true_positive", "manual_note": "old"},
                {"sample_id": "A002", "party_name": "VOX", "evidence_id": "4", "manual_label": "false_positive", "manual_note": "old"},
            ]
        )
        out = Path(tempfile.NamedTemporaryFile(delete=False, suffix=".csv").name)
        summary = Path(tempfile.NamedTemporaryFile(delete=False, suffix=".json").name)
        try:
            rc = target.main(
                [
                    "--sample-in",
                    str(sample),
                    "--labels-in",
                    str(labels),
                    "--out",
                    str(out),
                    "--summary-out",
                    str(summary),
                ]
            )
            self.assertEqual(rc, 0)
            with out.open("r", encoding="utf-8", newline="") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(rows[0]["manual_label"], "true_positive")
            self.assertIn("carry_forward", rows[0]["manual_note"])
            self.assertEqual(rows[1]["manual_label"], "")
            self.assertEqual(rows[2]["manual_label"], "true_positive")
            payload = json.loads(summary.read_text(encoding="utf-8"))
            self.assertEqual(int(payload["carried_forward_rows"]), 1)
            self.assertEqual(int(payload["unlabeled_rows"]), 1)
            self.assertEqual(payload["status"], "ok")
        finally:
            sample.unlink(missing_ok=True)
            labels.unlink(missing_ok=True)
            out.unlink(missing_ok=True)
            summary.unlink(missing_ok=True)

    def test_strict_fails_when_unlabeled_exceeds_max(self) -> None:
        sample = self._write_csv(
            [{"sample_id": "S001", "party_name": "BNG", "evidence_id": "100", "manual_label": "", "manual_note": ""}]
        )
        labels = self._write_csv([])
        out = Path(tempfile.NamedTemporaryFile(delete=False, suffix=".csv").name)
        try:
            rc = target.main(
                [
                    "--sample-in",
                    str(sample),
                    "--labels-in",
                    str(labels),
                    "--out",
                    str(out),
                    "--strict",
                    "--max-unlabeled",
                    "0",
                ]
            )
            self.assertEqual(rc, 4)
        finally:
            sample.unlink(missing_ok=True)
            labels.unlink(missing_ok=True)
            out.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
