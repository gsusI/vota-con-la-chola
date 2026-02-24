from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from etl.parlamentario_es.db import apply_schema, open_db
from scripts.export_sanction_procedural_official_review_apply_template import (
    build_template_rows,
)
from scripts.import_sanction_data_catalog_seed import import_seed as import_catalog_seed


class TestExportSanctionProceduralOfficialReviewApplyTemplate(unittest.TestCase):
    def _seed_catalog(self, conn: object) -> None:
        seed_path = Path(__file__).resolve().parents[1] / "etl" / "data" / "seeds" / "sanction_data_catalog_seed_v1.json"
        seed_doc = json.loads(seed_path.read_text(encoding="utf-8"))
        import_catalog_seed(conn, seed_doc=seed_doc, source_id="", snapshot_date="2026-02-24")

    def test_build_template_rows_emits_full_matrix(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "template_full.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                self._seed_catalog(conn)

                got = build_template_rows(
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
        self.assertEqual(int(got["counts"]["kpis_total"]), 3)
        self.assertEqual(int(got["counts"]["rows_emitted_total"]), 12)
        self.assertEqual(int(got["counts"]["rows_skipped_existing_total"]), 0)

        preview = list(got["rows_preview"])
        self.assertGreaterEqual(len(preview), 1)
        row = preview[0]
        self.assertEqual(str(row["period_date"]), "2025-12-31")
        self.assertEqual(str(row["period_granularity"]), "year")
        self.assertEqual(str(row["source_id"]), "boe_api_legal")
        self.assertEqual(str(row["evidence_date"]), "")
        self.assertEqual(str(row["evidence_quote"]), "")
        self.assertIn("official_review:", str(row["source_record_id"]))
        self.assertIn("|", str(row["metric_key"]))

    def test_build_template_rows_only_missing_skips_existing_metric(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "template_missing.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                self._seed_catalog(conn)

                conn.execute(
                    """
                    INSERT INTO sanction_procedural_metrics (
                      metric_key, kpi_id, sanction_source_id, period_date, period_granularity,
                      value, numerator, denominator, source_id, source_url, source_record_pk,
                      raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "kpi:recurso_estimation_rate|es:sanctions:teac_resolutions|2025-12-31|year",
                        "kpi:recurso_estimation_rate",
                        "es:sanctions:teac_resolutions",
                        "2025-12-31",
                        "year",
                        0.2,
                        20.0,
                        100.0,
                        None,
                        "https://sede.agenciatributaria.gob.es/",
                        None,
                        "{}",
                        "2026-02-24T00:00:00+00:00",
                        "2026-02-24T00:00:00+00:00",
                    ),
                )
                conn.commit()

                got = build_template_rows(
                    conn,
                    period_date="2025-12-31",
                    period_granularity="year",
                    default_source_id="boe_api_legal",
                    only_missing=True,
                )
            finally:
                conn.close()

        self.assertEqual(int(got["counts"]["rows_emitted_total"]), 11)
        self.assertEqual(int(got["counts"]["rows_skipped_existing_total"]), 1)


if __name__ == "__main__":
    unittest.main()
