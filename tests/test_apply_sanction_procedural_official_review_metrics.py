from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from etl.parlamentario_es.db import apply_schema, open_db
from scripts.apply_sanction_procedural_official_review_metrics import apply_rows
from scripts.import_sanction_data_catalog_seed import import_seed as import_catalog_seed


class TestApplySanctionProceduralOfficialReviewMetrics(unittest.TestCase):
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

    def test_apply_rows_dry_run_keeps_db_unchanged(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "dry_run.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                self._insert_source(conn)
                self._seed_catalog(conn)

                got = apply_rows(
                    conn,
                    rows=[
                        {
                            "sanction_source_id": "es:sanctions:teac_resolutions",
                            "kpi_id": "kpi:recurso_estimation_rate",
                            "period_date": "2025-12-31",
                            "period_granularity": "year",
                            "value": "0.24",
                            "numerator": "24",
                            "denominator": "100",
                            "source_url": "https://example.org/teac/2025",
                            "evidence_date": "2025-12-31",
                            "evidence_quote": "Memoria oficial TEAC 2025, apartado de estimación de recursos.",
                        },
                        {
                            "sanction_source_id": "",
                            "kpi_id": "kpi:recurso_estimation_rate",
                            "period_date": "2025-12-31",
                            "value": "0.1",
                            "source_url": "https://example.org/missing",
                            "evidence_date": "2025-12-31",
                            "evidence_quote": "Fila incompleta para validar skip por required fields.",
                        },
                    ],
                    default_source_id="boe_api_legal",
                    snapshot_date="2026-02-24",
                    dry_run=True,
                )

                metric_rows = conn.execute("SELECT COUNT(*) AS n FROM sanction_procedural_metrics").fetchone()
            finally:
                conn.close()

        self.assertEqual(int(got["counts"]["rows_seen"]), 2)
        self.assertEqual(int(got["counts"]["rows_ready"]), 1)
        self.assertEqual(int(got["counts"]["rows_upserted"]), 0)
        self.assertEqual(int(got["counts"]["source_record_pk_would_create"]), 1)
        self.assertEqual(int(got["counts"]["skipped_missing_required"]), 1)
        self.assertEqual(int(metric_rows["n"]), 0)

    def test_apply_rows_inserts_and_updates(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "apply.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                self._insert_source(conn)
                self._seed_catalog(conn)

                first = apply_rows(
                    conn,
                    rows=[
                        {
                            "sanction_source_id": "es:sanctions:teac_resolutions",
                            "kpi_id": "kpi:recurso_estimation_rate",
                            "period_date": "2025-12-31",
                            "period_granularity": "year",
                            "value": "0.20",
                            "numerator": "20",
                            "denominator": "100",
                            "source_url": "https://example.org/teac/2025",
                            "evidence_date": "2025-12-31",
                            "evidence_quote": "Memoria oficial TEAC 2025, tabla anual consolidada.",
                            "source_record_id": "teac:2025:recurso_estimation_rate",
                        }
                    ],
                    default_source_id="boe_api_legal",
                    snapshot_date="2026-02-24",
                    dry_run=False,
                )

                second = apply_rows(
                    conn,
                    rows=[
                        {
                            "sanction_source_id": "es:sanctions:teac_resolutions",
                            "kpi_id": "kpi:recurso_estimation_rate",
                            "period_date": "2025-12-31",
                            "period_granularity": "year",
                            "value": "0.21",
                            "numerator": "21",
                            "denominator": "100",
                            "source_url": "https://example.org/teac/2025",
                            "evidence_date": "2025-12-31",
                            "evidence_quote": "Actualización TEAC 2025, misma tabla de recursos con revisión final.",
                            "source_record_id": "teac:2025:recurso_estimation_rate",
                        }
                    ],
                    default_source_id="boe_api_legal",
                    snapshot_date="2026-02-24",
                    dry_run=False,
                )

                row = conn.execute(
                    """
                    SELECT value, numerator, denominator, source_record_pk, evidence_date, evidence_quote
                    FROM sanction_procedural_metrics
                    WHERE metric_key = ?
                    """,
                    ("kpi:recurso_estimation_rate|es:sanctions:teac_resolutions|2025-12-31|year",),
                ).fetchone()
                sr = conn.execute(
                    "SELECT source_record_id FROM source_records WHERE source_record_pk = ?",
                    (int(row["source_record_pk"]),),
                ).fetchone()
            finally:
                conn.close()

        self.assertEqual(int(first["counts"]["inserted_rows"]), 1)
        self.assertEqual(int(first["counts"]["source_record_pk_auto_created"]), 1)
        self.assertEqual(int(second["counts"]["updated_rows"]), 1)
        self.assertEqual(int(second["counts"]["source_record_pk_auto_resolved"]), 1)
        self.assertAlmostEqual(float(row["value"]), 0.21, places=6)
        self.assertAlmostEqual(float(row["numerator"]), 21.0, places=6)
        self.assertAlmostEqual(float(row["denominator"]), 100.0, places=6)
        self.assertEqual(str(row["evidence_date"]), "2025-12-31")
        self.assertIn("Actualización TEAC 2025", str(row["evidence_quote"]))
        self.assertEqual(str(sr["source_record_id"]), "teac:2025:recurso_estimation_rate")


if __name__ == "__main__":
    unittest.main()
