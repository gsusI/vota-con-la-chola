from __future__ import annotations

import unittest

from scripts.report_liberty_delegated_person_window_auto_review_qa_precision import build_precision_report


class TestReportLibertyDelegatedPersonWindowAutoReviewQaPrecision(unittest.TestCase):
    def test_build_precision_report_counts_confirm_reject(self) -> None:
        qa_rows = [
            {
                "link_key": "k1",
                "delegated_institution_label": "AEAT",
                "qa_decision": "confirm",
            },
            {
                "link_key": "k2",
                "delegated_institution_label": "AEAT",
                "qa_decision": "reject",
            },
            {
                "link_key": "k3",
                "delegated_institution_label": "DGT",
                "qa_decision": "confirm",
            },
            {
                "link_key": "k4",
                "delegated_institution_label": "DGT",
                "qa_decision": "",
            },
        ]

        got = build_precision_report(
            qa_rows=qa_rows,
            min_reviewed_rows=3,
            min_precision_pct=60.0,
            decision_scope="all",
            strict=True,
        )

        report = got
        self.assertEqual(report["status"], "ok")
        self.assertEqual(int(report["rows_total"]), 4)
        self.assertEqual(int(report["reviewed_rows_total"]), 3)
        self.assertEqual(int(report["confirm_total"]), 2)
        self.assertEqual(int(report["reject_total"]), 1)
        self.assertEqual(float(report["observed_precision_pct"]), 66.6667)
        self.assertEqual(report["strict_fail_reasons"], [])

    def test_build_precision_report_flags_threshold_and_invalid_decision(self) -> None:
        qa_rows = [
            {
                "link_key": "k1",
                "delegated_institution_label": "AEAT",
                "qa_decision": "confirm",
            },
            {
                "link_key": "k2",
                "delegated_institution_label": "AEAT",
                "qa_decision": "oops",
            },
        ]

        report = build_precision_report(
            qa_rows=qa_rows,
            min_reviewed_rows=2,
            min_precision_pct=101.0,
            decision_scope="all",
            strict=True,
        )

        self.assertEqual(report["status"], "degraded")
        reasons = set(report["strict_fail_reasons"])
        self.assertIn("reviewed_rows_below_min", reasons)
        self.assertIn("precision_below_min", reasons)
        self.assertIn("invalid_qa_decisions", reasons)
        self.assertEqual(int(report["invalid_decision_total"]), 1)

    def test_build_precision_report_scope_approved_filters_pending_rows(self) -> None:
        qa_rows = [
            {
                "link_key": "k1",
                "delegated_institution_label": "AEAT",
                "auto_decision": "approved",
                "qa_decision": "confirm",
            },
            {
                "link_key": "k2",
                "delegated_institution_label": "AEAT",
                "auto_decision": "pending",
                "qa_decision": "reject",
            },
        ]

        report = build_precision_report(
            qa_rows=qa_rows,
            min_reviewed_rows=1,
            min_precision_pct=99.0,
            decision_scope="approved",
            strict=True,
        )

        self.assertEqual(report["status"], "ok")
        self.assertEqual(int(report["rows_total"]), 2)
        self.assertEqual(int(report["rows_in_scope_total"]), 1)
        self.assertEqual(int(report["rows_excluded_by_scope_total"]), 1)
        self.assertEqual(int(report["reviewed_rows_total"]), 1)
        self.assertEqual(float(report["observed_precision_pct"]), 100.0)


if __name__ == "__main__":
    unittest.main()
