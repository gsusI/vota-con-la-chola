from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from etl.parlamentario_es.db import apply_schema, open_db
from scripts.export_sanction_procedural_official_review_raw_template import build_raw_template
from scripts.import_sanction_data_catalog_seed import import_seed as import_catalog_seed


class TestExportSanctionProceduralOfficialReviewRawTemplate(unittest.TestCase):
    def _seed_catalog(self, conn: object) -> None:
        seed_path = Path(__file__).resolve().parents[1] / "etl" / "data" / "seeds" / "sanction_data_catalog_seed_v1.json"
        seed_doc = json.loads(seed_path.read_text(encoding="utf-8"))
        import_catalog_seed(conn, seed_doc=seed_doc, source_id="", snapshot_date="2026-02-24")

    def test_build_raw_template_emits_all_sources(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "raw_template_full.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                self._seed_catalog(conn)

                got = build_raw_template(
                    conn,
                    period_date="2025-12-31",
                    period_granularity="year",
                    default_source_id="boe_api_legal",
                    only_missing=False,
                )
            finally:
                conn.close()

        self.assertEqual(int(got["counts"]["sources_expected_total"]), 4)
        self.assertEqual(int(got["counts"]["sources_seeded_total"]), 4)
        self.assertEqual(int(got["counts"]["rows_emitted_total"]), 4)
        self.assertEqual(int(got["counts"]["rows_skipped_fully_covered_total"]), 0)

        row = list(got["rows_preview"])[0]
        self.assertEqual(str(row["period_date"]), "2025-12-31")
        self.assertEqual(str(row["period_granularity"]), "year")
        self.assertEqual(str(row["source_id"]), "boe_api_legal")
        self.assertEqual(str(row["evidence_date"]), "")
        self.assertEqual(str(row["evidence_quote"]), "")
        self.assertIn("official_review_raw:", str(row["source_record_id"]))
        self.assertGreaterEqual(len(str(row["procedural_kpis_expected"]).split(",")), 3)

    def test_build_raw_template_only_missing_skips_covered_source(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "raw_template_missing.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                self._seed_catalog(conn)

                ts = "2026-02-24T00:00:00+00:00"
                src = "es:sanctions:teac_resolutions"
                period_date = "2025-12-31"
                period_granularity = "year"
                rows = [
                    (
                        f"kpi:recurso_estimation_rate|{src}|{period_date}|{period_granularity}",
                        "kpi:recurso_estimation_rate",
                        0.2,
                        20.0,
                        100.0,
                    ),
                    (
                        f"kpi:formal_annulment_rate|{src}|{period_date}|{period_granularity}",
                        "kpi:formal_annulment_rate",
                        0.05,
                        5.0,
                        100.0,
                    ),
                    (
                        f"kpi:resolution_delay_p90_days|{src}|{period_date}|{period_granularity}",
                        "kpi:resolution_delay_p90_days",
                        120.0,
                        None,
                        None,
                    ),
                ]
                for metric_key, kpi_id, value, numerator, denominator in rows:
                    conn.execute(
                        """
                        INSERT INTO sanction_procedural_metrics (
                          metric_key, kpi_id, sanction_source_id, period_date, period_granularity,
                          value, numerator, denominator, source_id, source_url, source_record_pk,
                          raw_payload, created_at, updated_at, evidence_date, evidence_quote
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            metric_key,
                            kpi_id,
                            src,
                            period_date,
                            period_granularity,
                            value,
                            numerator,
                            denominator,
                            None,
                            "https://example.org/teac/2025",
                            None,
                            "{}",
                            ts,
                            ts,
                            "2025-12-31",
                            "Evidencia oficial TEAC 2025 para cobertura de KPI.",
                        ),
                    )
                conn.commit()

                got = build_raw_template(
                    conn,
                    period_date=period_date,
                    period_granularity=period_granularity,
                    default_source_id="boe_api_legal",
                    only_missing=True,
                )
            finally:
                conn.close()

        self.assertEqual(int(got["counts"]["rows_emitted_total"]), 3)
        self.assertEqual(int(got["counts"]["rows_skipped_fully_covered_total"]), 1)


if __name__ == "__main__":
    unittest.main()
