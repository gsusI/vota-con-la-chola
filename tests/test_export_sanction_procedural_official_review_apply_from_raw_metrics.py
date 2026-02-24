from __future__ import annotations

import unittest

from scripts.export_sanction_procedural_official_review_apply_from_raw_metrics import build_apply_rows


class TestExportSanctionProceduralOfficialReviewApplyFromRawMetrics(unittest.TestCase):
    def test_build_apply_rows_ok_emits_three_kpis_per_input_row(self) -> None:
        headers = [
            "sanction_source_id",
            "period_date",
            "period_granularity",
            "source_url",
            "evidence_date",
            "evidence_quote",
            "recurso_presentado_count",
            "recurso_estimado_count",
            "anulaciones_formales_count",
            "resolution_delay_p90_days",
            "source_id",
            "source_record_id",
        ]
        rows = [
            {
                "sanction_source_id": "es:sanctions:teac_resolutions",
                "period_date": "2025-12-31",
                "period_granularity": "year",
                "source_url": "https://example.org/teac/2025",
                "evidence_date": "2025-12-31",
                "evidence_quote": "Memoria oficial TEAC 2025, consolidado anual de recursos y anulaciones.",
                "recurso_presentado_count": "100",
                "recurso_estimado_count": "20",
                "anulaciones_formales_count": "5",
                "resolution_delay_p90_days": "120",
                "source_id": "boe_api_legal",
                "source_record_id": "teac:2025",
            }
        ]

        got = build_apply_rows(
            headers=headers,
            rows=rows,
            default_source_id="boe_api_legal",
            default_period_granularity="year",
        )

        self.assertEqual(str(got["status"]), "ok")
        self.assertEqual(int(got["totals"]["rows_seen"]), 1)
        self.assertEqual(int(got["totals"]["rows_emitted"]), 1)
        self.assertEqual(int(got["totals"]["kpi_rows_emitted"]), 3)
        self.assertEqual(len(got["apply_rows"]), 3)
        self.assertEqual(len(got["rejected_rows"]), 0)

        by_kpi = {str(row["kpi_id"]): row for row in got["apply_rows"]}
        self.assertEqual(float(by_kpi["kpi:recurso_estimation_rate"]["value"]), 0.2)
        self.assertEqual(float(by_kpi["kpi:formal_annulment_rate"]["value"]), 0.05)
        self.assertEqual(float(by_kpi["kpi:resolution_delay_p90_days"]["value"]), 120.0)
        self.assertEqual(str(by_kpi["kpi:recurso_estimation_rate"]["source_record_id"]), "teac:2025:kpi-recurso-estimation-rate")
        self.assertEqual(str(by_kpi["kpi:formal_annulment_rate"]["source_record_id"]), "teac:2025:kpi-formal-annulment-rate")
        self.assertEqual(str(by_kpi["kpi:resolution_delay_p90_days"]["source_record_id"]), "teac:2025:kpi-resolution-delay-p90-days")

    def test_build_apply_rows_degraded_for_invalid_row(self) -> None:
        headers = [
            "sanction_source_id",
            "period_date",
            "source_url",
            "evidence_date",
            "evidence_quote",
            "recurso_presentado_count",
            "recurso_estimado_count",
            "anulaciones_formales_count",
            "resolution_delay_p90_days",
        ]
        rows = [
            {
                "sanction_source_id": "es:sanctions:teac_resolutions",
                "period_date": "2025-12-31",
                "source_url": "https://example.org/teac/2025",
                "evidence_date": "31-12-2025",
                "evidence_quote": "short",
                "recurso_presentado_count": "0",
                "recurso_estimado_count": "1",
                "anulaciones_formales_count": "-1",
                "resolution_delay_p90_days": "0",
            }
        ]

        got = build_apply_rows(
            headers=headers,
            rows=rows,
            default_source_id="boe_api_legal",
            default_period_granularity="year",
        )

        self.assertEqual(str(got["status"]), "degraded")
        self.assertEqual(int(got["totals"]["rows_emitted"]), 0)
        self.assertEqual(int(got["totals"]["rows_rejected"]), 1)
        self.assertEqual(len(got["apply_rows"]), 0)
        self.assertEqual(len(got["rejected_rows"]), 1)

        reason = str(got["rejected_rows"][0]["_reason"])
        self.assertIn("invalid_evidence_date", reason)
        self.assertIn("short_evidence_quote", reason)
        self.assertIn("non_positive_recurso_presentado_count", reason)
        self.assertIn("negative_component_count", reason)
        self.assertIn("non_positive_resolution_delay_p90_days", reason)

    def test_build_apply_rows_failed_when_required_headers_missing(self) -> None:
        headers = [
            "sanction_source_id",
            "period_date",
            "source_url",
            "evidence_date",
            "evidence_quote",
            "recurso_presentado_count",
        ]
        rows = [
            {
                "sanction_source_id": "es:sanctions:teac_resolutions",
                "period_date": "2025-12-31",
                "source_url": "https://example.org/teac/2025",
                "evidence_date": "2025-12-31",
                "evidence_quote": "Memoria oficial TEAC 2025, consolidado anual de recursos y anulaciones.",
                "recurso_presentado_count": "100",
            }
        ]

        got = build_apply_rows(
            headers=headers,
            rows=rows,
            default_source_id="boe_api_legal",
            default_period_granularity="year",
        )

        self.assertEqual(str(got["status"]), "failed")
        self.assertIn("recurso_estimado_count", list(got["missing_headers"]))
        self.assertFalse(bool(got["checks"]["headers_complete"]))


if __name__ == "__main__":
    unittest.main()
