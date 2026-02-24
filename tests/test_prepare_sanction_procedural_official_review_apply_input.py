from __future__ import annotations

import unittest

from scripts.prepare_sanction_procedural_official_review_apply_input import (
    build_prepare_report,
)


class TestPrepareSanctionProceduralOfficialReviewApplyInput(unittest.TestCase):
    def test_ok_when_rows_have_value_and_required_fields(self) -> None:
        got = build_prepare_report(
            headers=[
                "sanction_source_id",
                "kpi_id",
                "period_date",
                "source_url",
                "evidence_date",
                "evidence_quote",
                "value",
                "numerator",
                "denominator",
            ],
            rows=[
                {
                    "sanction_source_id": "es:sanctions:teac_resolutions",
                    "kpi_id": "kpi:recurso_estimation_rate",
                    "period_date": "2025-12-31",
                    "source_url": "https://example.org/teac",
                    "evidence_date": "2025-12-31",
                    "evidence_quote": "Memoria oficial TEAC 2025, tabla de recursos estimados.",
                    "value": "0.2",
                    "numerator": "20",
                    "denominator": "100",
                }
            ],
        )
        self.assertEqual(str(got["status"]), "ok")
        self.assertEqual(int(got["totals"]["rows_kept"]), 1)
        self.assertEqual(int(got["totals"]["rows_rejected"]), 0)

    def test_degraded_when_only_empty_template_rows(self) -> None:
        got = build_prepare_report(
            headers=[
                "sanction_source_id",
                "kpi_id",
                "period_date",
                "source_url",
                "evidence_date",
                "evidence_quote",
                "value",
                "numerator",
                "denominator",
            ],
            rows=[
                {
                    "sanction_source_id": "es:sanctions:teac_resolutions",
                    "kpi_id": "kpi:recurso_estimation_rate",
                    "period_date": "2025-12-31",
                    "source_url": "https://example.org/teac",
                    "evidence_date": "2025-12-31",
                    "evidence_quote": "Memoria oficial TEAC 2025, tabla de recursos estimados.",
                    "value": "",
                    "numerator": "",
                    "denominator": "",
                }
            ],
        )
        self.assertEqual(str(got["status"]), "degraded")
        self.assertEqual(int(got["totals"]["rows_kept"]), 0)
        self.assertEqual(int(got["totals"]["rows_rejected"]), 1)
        self.assertEqual(int(got["totals"]["rows_rejected_missing_value"]), 1)

    def test_failed_when_required_headers_missing(self) -> None:
        got = build_prepare_report(
            headers=["sanction_source_id", "kpi_id", "period_date", "value"],
            rows=[
                {
                    "sanction_source_id": "es:sanctions:teac_resolutions",
                    "kpi_id": "kpi:recurso_estimation_rate",
                    "period_date": "2025-12-31",
                    "value": "0.2",
                }
            ],
        )
        self.assertEqual(str(got["status"]), "failed")
        self.assertIn("source_url", list(got["missing_headers"]))


if __name__ == "__main__":
    unittest.main()
