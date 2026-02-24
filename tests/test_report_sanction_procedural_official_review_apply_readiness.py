from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from etl.parlamentario_es.db import apply_schema, open_db
from scripts.import_sanction_data_catalog_seed import import_seed as import_catalog_seed
from scripts.report_sanction_procedural_official_review_apply_readiness import build_report


class TestReportSanctionProceduralOfficialReviewApplyReadiness(unittest.TestCase):
    def _insert_source(self, conn: object, source_id: str = "boe_api_legal") -> None:
        ts = "2026-02-24T00:00:00+00:00"
        conn.execute(
            """
            INSERT INTO sources (
              source_id, name, scope, default_url, data_format, is_active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                "BOE API Legal",
                "nacional",
                "https://www.boe.es/",
                "json",
                1,
                ts,
                ts,
            ),
        )
        conn.commit()

    def _seed_catalog(self, conn: object) -> None:
        seed_path = Path(__file__).resolve().parents[1] / "etl" / "data" / "seeds" / "sanction_data_catalog_seed_v1.json"
        seed_doc = json.loads(seed_path.read_text(encoding="utf-8"))
        import_catalog_seed(conn, seed_doc=seed_doc, source_id="", snapshot_date="2026-02-24")

    def _setup_db(self, db_path: Path) -> object:
        conn = open_db(db_path)
        schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
        apply_schema(conn, schema_path)
        self._insert_source(conn)
        self._seed_catalog(conn)
        return conn

    def test_report_ok_for_valid_rows(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "readiness_ok.db"
            csv_path = Path(td) / "input.csv"
            with csv_path.open("w", encoding="utf-8", newline="") as fh:
                writer = csv.DictWriter(
                    fh,
                    fieldnames=[
                        "sanction_source_id",
                        "kpi_id",
                        "period_date",
                        "period_granularity",
                        "value",
                        "numerator",
                        "denominator",
                        "source_url",
                        "evidence_date",
                        "evidence_quote",
                        "source_id",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "sanction_source_id": "es:sanctions:teac_resolutions",
                        "kpi_id": "kpi:recurso_estimation_rate",
                        "period_date": "2025-12-31",
                        "period_granularity": "year",
                        "value": "0.2",
                        "numerator": "20",
                        "denominator": "100",
                        "source_url": "https://example.org/teac/2025",
                        "evidence_date": "2025-12-31",
                        "evidence_quote": "Memoria oficial TEAC 2025, sección de recursos estimados.",
                        "source_id": "boe_api_legal",
                    }
                )

            conn = self._setup_db(db_path)
            try:
                got = build_report(conn, input_csv=csv_path, tolerance=0.001)
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "ok")
        self.assertEqual(int(got["totals"]["rows_seen"]), 1)
        self.assertEqual(int(got["totals"]["rows_ready"]), 1)
        self.assertEqual(int(got["totals"]["rows_blocked"]), 0)
        self.assertEqual(len(got["queue"]), 0)

    def test_report_degraded_for_invalid_rows(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "readiness_bad.db"
            csv_path = Path(td) / "input.csv"
            with csv_path.open("w", encoding="utf-8", newline="") as fh:
                writer = csv.DictWriter(
                    fh,
                    fieldnames=[
                        "sanction_source_id",
                        "kpi_id",
                        "period_date",
                        "period_granularity",
                        "value",
                        "numerator",
                        "denominator",
                        "source_url",
                        "evidence_date",
                        "evidence_quote",
                        "source_id",
                        "metric_key",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "sanction_source_id": "es:sanctions:teac_resolutions",
                        "kpi_id": "kpi:recurso_estimation_rate",
                        "period_date": "2025-12-31",
                        "period_granularity": "year",
                        "value": "",
                        "numerator": "20",
                        "denominator": "100",
                        "source_url": "not-a-url",
                        "evidence_date": "31-12-2025",
                        "evidence_quote": "short",
                        "source_id": "boe_api_legal",
                        "metric_key": "dup_key",
                    }
                )
                writer.writerow(
                    {
                        "sanction_source_id": "es:sanctions:teac_resolutions",
                        "kpi_id": "kpi:recurso_estimation_rate",
                        "period_date": "2025-12-31",
                        "period_granularity": "year",
                        "value": "0.5",
                        "numerator": "20",
                        "denominator": "100",
                        "source_url": "https://example.org/teac/2025",
                        "evidence_date": "2025-12-31",
                        "evidence_quote": "Memoria oficial TEAC 2025, tabla anual consolidada de recursos.",
                        "source_id": "unknown_source",
                        "metric_key": "dup_key",
                    }
                )

            conn = self._setup_db(db_path)
            try:
                got = build_report(conn, input_csv=csv_path, tolerance=0.001)
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "degraded")
        self.assertEqual(int(got["totals"]["rows_seen"]), 2)
        self.assertEqual(int(got["totals"]["rows_blocked"]), 2)
        self.assertGreaterEqual(int(got["totals"]["rows_duplicate_metric_key"]), 1)
        self.assertGreaterEqual(int(got["totals"]["rows_invalid_source_url"]), 1)
        self.assertGreaterEqual(int(got["totals"]["rows_invalid_source_id"]), 1)
        self.assertGreaterEqual(int(got["totals"]["rows_invalid_evidence_date"]), 1)
        self.assertGreaterEqual(int(got["totals"]["rows_short_evidence_quote"]), 1)
        self.assertGreaterEqual(int(got["totals"]["rows_formula_mismatch"]), 1)
        self.assertGreaterEqual(len(got["queue"]), 1)

    def test_report_failed_when_required_headers_missing(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "readiness_missing_header.db"
            csv_path = Path(td) / "input.csv"
            with csv_path.open("w", encoding="utf-8", newline="") as fh:
                writer = csv.DictWriter(
                    fh,
                    fieldnames=[
                        "sanction_source_id",
                        "kpi_id",
                        "period_date",
                        "period_granularity",
                        "numerator",
                        "denominator",
                        "source_url",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "sanction_source_id": "es:sanctions:teac_resolutions",
                        "kpi_id": "kpi:recurso_estimation_rate",
                        "period_date": "2025-12-31",
                        "period_granularity": "year",
                        "numerator": "20",
                        "denominator": "100",
                        "source_url": "https://example.org/teac/2025",
                    }
                )

            conn = self._setup_db(db_path)
            try:
                got = build_report(conn, input_csv=csv_path, tolerance=0.001)
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "failed")
        self.assertFalse(bool(got["checks"]["headers_complete"]))
        self.assertIn("value", list(got["missing_headers"]))


if __name__ == "__main__":
    unittest.main()
