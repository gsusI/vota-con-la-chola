from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import report_liberty_delegated_non_nominative_qa_gate as target


class ReportLibertyDelegatedNonNominativeQaGateTests(unittest.TestCase):
    def test_gate_not_required_when_fallback_count_is_zero(self) -> None:
        report = target.build_report(
            auto_review_payload={"summary": {"approved_with_non_nominative_actor_fallback_total": 0}},
            qa_sample_summary_payload={},
            qa_precision_payload={},
            review_note_contains="approved_non_nominative_unit",
            min_reviewed_rows=1,
            min_precision_pct=100.0,
        )
        self.assertEqual(report["status"], "ok")
        self.assertFalse(report["qa_required"])
        self.assertEqual(report["strict_fail_reasons"], [])

    def test_gate_requires_and_accepts_matching_qa_outputs(self) -> None:
        report = target.build_report(
            auto_review_payload={
                "summary": {"approved_with_non_nominative_actor_fallback_total": 1},
                "out_csv": "auto.csv",
            },
            qa_sample_summary_payload={
                "auto_review_csv": "auto.csv",
                "out_csv": "qa_sample_latest.csv",
                "summary": {
                    "sample_rows_total": 1,
                    "review_note_contains": "approved_non_nominative_unit",
                }
            },
            qa_precision_payload={
                "qa_csv": "qa_sample_reviewed_latest.csv",
                "report": {
                    "status": "ok",
                    "reviewed_rows_total": 1,
                    "observed_precision_pct": 100.0,
                    "strict_fail_reasons": [],
                }
            },
            review_note_contains="approved_non_nominative_unit",
            min_reviewed_rows=1,
            min_precision_pct=100.0,
        )
        self.assertEqual(report["status"], "ok")
        self.assertTrue(report["qa_required"])
        self.assertEqual(report["strict_fail_reasons"], [])

    def test_gate_degraded_when_precision_below_threshold(self) -> None:
        report = target.build_report(
            auto_review_payload={
                "summary": {"approved_with_non_nominative_actor_fallback_total": 1},
                "out_csv": "auto.csv",
            },
            qa_sample_summary_payload={
                "auto_review_csv": "auto.csv",
                "out_csv": "qa.csv",
                "summary": {
                    "sample_rows_total": 1,
                    "review_note_contains": "approved_non_nominative_unit",
                }
            },
            qa_precision_payload={
                "qa_csv": "qa.csv",
                "report": {
                    "status": "ok",
                    "reviewed_rows_total": 1,
                    "observed_precision_pct": 50.0,
                    "strict_fail_reasons": [],
                }
            },
            review_note_contains="approved_non_nominative_unit",
            min_reviewed_rows=1,
            min_precision_pct=100.0,
        )
        self.assertEqual(report["status"], "degraded")
        self.assertIn("qa_precision_below_min", report["strict_fail_reasons"])

    def test_gate_degraded_when_qa_sample_not_linked_to_auto_review(self) -> None:
        report = target.build_report(
            auto_review_payload={
                "summary": {"approved_with_non_nominative_actor_fallback_total": 1},
                "out_csv": "auto_latest.csv",
            },
            qa_sample_summary_payload={
                "auto_review_csv": "auto_old.csv",
                "out_csv": "qa.csv",
                "summary": {
                    "sample_rows_total": 1,
                    "review_note_contains": "approved_non_nominative_unit",
                },
            },
            qa_precision_payload={
                "qa_csv": "qa.csv",
                "report": {
                    "status": "ok",
                    "reviewed_rows_total": 1,
                    "observed_precision_pct": 100.0,
                    "strict_fail_reasons": [],
                },
            },
            review_note_contains="approved_non_nominative_unit",
            min_reviewed_rows=1,
            min_precision_pct=100.0,
        )
        self.assertEqual(report["status"], "degraded")
        self.assertIn("qa_sample_not_linked_to_auto_review", report["strict_fail_reasons"])

    def test_main_strict_returns_4_when_required_qa_files_missing(self) -> None:
        auto_file = Path(tempfile.NamedTemporaryFile(delete=False, suffix=".json").name)
        out_file = Path(tempfile.NamedTemporaryFile(delete=False, suffix=".json").name)
        try:
            auto_file.write_text(
                json.dumps(
                    {"summary": {"approved_with_non_nominative_actor_fallback_total": 2}},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            rc = target.main(
                [
                    "--auto-review-summary",
                    str(auto_file),
                    "--strict",
                    "--out",
                    str(out_file),
                ]
            )
            self.assertEqual(rc, 4)
            payload = json.loads(out_file.read_text(encoding="utf-8"))
            self.assertEqual(payload["report"]["status"], "degraded")
            self.assertIn("missing_qa_sample_summary", payload["report"]["strict_fail_reasons"])
            self.assertIn("missing_qa_precision_report", payload["report"]["strict_fail_reasons"])
        finally:
            auto_file.unlink(missing_ok=True)
            out_file.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
