from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from etl.parlamentario_es.db import apply_schema, open_db
from scripts.import_sanction_data_catalog_seed import import_seed as import_catalog_seed
from scripts.report_sanction_procedural_official_review_status import (
    OFFICIAL_REVIEW_SOURCE_IDS,
    build_status_report,
)


class TestReportSanctionProceduralOfficialReviewStatus(unittest.TestCase):
    def _insert_source(self, conn: object, source_id: str = "boe_api_legal") -> None:
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
                "2026-02-24T00:00:00+00:00",
                "2026-02-24T00:00:00+00:00",
            ),
        )
        conn.commit()

    def _insert_source_record(self, conn: object, source_record_id: str) -> int:
        conn.execute(
            """
            INSERT INTO source_records (
              source_id, source_record_id, source_snapshot_date, raw_payload, content_sha256, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "boe_api_legal",
                source_record_id,
                "2026-02-24",
                "{}",
                f"sha-{source_record_id}",
                "2026-02-24T00:00:00+00:00",
                "2026-02-24T00:00:00+00:00",
            ),
        )
        conn.commit()
        return int(
            conn.execute(
                """
                SELECT source_record_pk
                FROM source_records
                WHERE source_id = ? AND source_record_id = ?
                """,
                ("boe_api_legal", source_record_id),
            ).fetchone()["source_record_pk"]
        )

    def _insert_metric(
        self,
        conn: object,
        *,
        metric_key: str,
        kpi_id: str,
        sanction_source_id: str,
        period_date: str,
        source_record_pk: int,
    ) -> None:
        conn.execute(
            """
            INSERT INTO sanction_procedural_metrics (
              metric_key, kpi_id, sanction_source_id, period_date, period_granularity,
              value, numerator, denominator, source_id, source_url, source_record_pk,
              evidence_date, evidence_quote, raw_payload, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                metric_key,
                kpi_id,
                sanction_source_id,
                period_date,
                "year",
                0.21 if kpi_id != "kpi:resolution_delay_p90_days" else 120.0,
                21.0 if kpi_id != "kpi:resolution_delay_p90_days" else None,
                100.0 if kpi_id != "kpi:resolution_delay_p90_days" else None,
                "boe_api_legal",
                "https://sede.agenciatributaria.gob.es/",
                source_record_pk,
                period_date,
                "Evidencia oficial para validar cobertura KPI en status lane.",
                "{}",
                "2026-02-24T00:00:00+00:00",
                "2026-02-24T00:00:00+00:00",
            ),
        )
        conn.commit()

    def test_report_failed_when_sources_not_seeded(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "status_empty.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                got = build_status_report(conn)
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "failed")
        self.assertEqual(int(got["totals"]["official_review_sources_expected_total"]), len(OFFICIAL_REVIEW_SOURCE_IDS))
        self.assertEqual(int(got["totals"]["official_review_sources_seeded_total"]), 0)
        self.assertEqual(int(got["totals"]["official_review_sources_missing_total"]), len(OFFICIAL_REVIEW_SOURCE_IDS))

    def test_report_degraded_when_seeded_but_without_metrics(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "status_seeded.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)

                data_seed_path = Path(__file__).resolve().parents[1] / "etl" / "data" / "seeds" / "sanction_data_catalog_seed_v1.json"
                data_seed_doc = json.loads(data_seed_path.read_text(encoding="utf-8"))
                import_catalog_seed(conn, seed_doc=data_seed_doc, source_id="", snapshot_date="2026-02-24")

                got = build_status_report(conn)
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "degraded")
        self.assertTrue(bool(got["checks"]["official_review_sources_seeded"]))
        self.assertFalse(bool(got["checks"]["official_review_metrics_started"]))
        self.assertEqual(int(got["totals"]["official_review_sources_seeded_total"]), len(OFFICIAL_REVIEW_SOURCE_IDS))
        self.assertEqual(int(got["totals"]["official_review_procedural_metrics_total"]), 0)

    def test_report_queue_highlights_source_record_gap(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "status_metrics.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)

                data_seed_path = Path(__file__).resolve().parents[1] / "etl" / "data" / "seeds" / "sanction_data_catalog_seed_v1.json"
                data_seed_doc = json.loads(data_seed_path.read_text(encoding="utf-8"))
                import_catalog_seed(conn, seed_doc=data_seed_doc, source_id="", snapshot_date="2026-02-24")

                conn.execute(
                    """
                    INSERT INTO sanction_procedural_metrics (
                      metric_key, kpi_id, sanction_source_id, period_date, period_granularity,
                      value, numerator, denominator, source_id, source_url, source_record_pk,
                      raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "kpi:recurso_estimation_rate|es:sanctions:teac_resolutions|2025-12-31",
                        "kpi:recurso_estimation_rate",
                        "es:sanctions:teac_resolutions",
                        "2025-12-31",
                        "year",
                        0.21,
                        21.0,
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

                got = build_status_report(conn)
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "degraded")
        self.assertEqual(int(got["totals"]["official_review_procedural_metrics_total"]), 1)
        self.assertEqual(int(got["totals"]["official_review_sources_with_metrics_total"]), 1)
        self.assertEqual(int(got["totals"]["official_review_metric_rows_missing_source_record_total"]), 1)

        queue_by_source = {str(row["sanction_source_id"]): row for row in got["queue"]}
        teac = queue_by_source["es:sanctions:teac_resolutions"]
        self.assertEqual(str(teac["status"]), "no_source_record_chain")
        self.assertEqual(str(teac["next_action"]), "backfill_source_record_pk_for_official_review_metrics")

    def test_report_queue_highlights_evidence_gap(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "status_metrics_evidence_gap.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)

                data_seed_path = Path(__file__).resolve().parents[1] / "etl" / "data" / "seeds" / "sanction_data_catalog_seed_v1.json"
                data_seed_doc = json.loads(data_seed_path.read_text(encoding="utf-8"))
                import_catalog_seed(conn, seed_doc=data_seed_doc, source_id="", snapshot_date="2026-02-24")

                conn.execute(
                    """
                    INSERT INTO sources (
                      source_id, name, scope, default_url, data_format, is_active, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "boe_api_legal",
                        "BOE API Legal",
                        "nacional",
                        "https://www.boe.es/",
                        "json",
                        1,
                        "2026-02-24T00:00:00+00:00",
                        "2026-02-24T00:00:00+00:00",
                    ),
                )

                conn.execute(
                    """
                    INSERT INTO source_records (
                      source_id, source_record_id, source_snapshot_date, raw_payload, content_sha256, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "boe_api_legal",
                        "teac:2025:recurso_estimation_rate",
                        "2026-02-24",
                        "{}",
                        "sha-test",
                        "2026-02-24T00:00:00+00:00",
                        "2026-02-24T00:00:00+00:00",
                    ),
                )
                source_record_pk = int(
                    conn.execute(
                        """
                        SELECT source_record_pk
                        FROM source_records
                        WHERE source_id = ? AND source_record_id = ?
                        """,
                        ("boe_api_legal", "teac:2025:recurso_estimation_rate"),
                    ).fetchone()["source_record_pk"]
                )

                conn.execute(
                    """
                    INSERT INTO sanction_procedural_metrics (
                      metric_key, kpi_id, sanction_source_id, period_date, period_granularity,
                      value, numerator, denominator, source_id, source_url, source_record_pk,
                      evidence_date, evidence_quote, raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "kpi:recurso_estimation_rate|es:sanctions:teac_resolutions|2025-12-31",
                        "kpi:recurso_estimation_rate",
                        "es:sanctions:teac_resolutions",
                        "2025-12-31",
                        "year",
                        0.21,
                        21.0,
                        100.0,
                        "boe_api_legal",
                        "https://sede.agenciatributaria.gob.es/",
                        source_record_pk,
                        None,
                        None,
                        "{}",
                        "2026-02-24T00:00:00+00:00",
                        "2026-02-24T00:00:00+00:00",
                    ),
                )
                conn.commit()

                got = build_status_report(conn)
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "degraded")
        self.assertEqual(int(got["totals"]["official_review_procedural_metrics_total"]), 1)
        self.assertEqual(int(got["totals"]["official_review_metric_rows_with_source_record_total"]), 1)
        self.assertEqual(int(got["totals"]["official_review_metric_rows_missing_evidence_total"]), 1)

        queue_by_source = {str(row["sanction_source_id"]): row for row in got["queue"]}
        teac = queue_by_source["es:sanctions:teac_resolutions"]
        self.assertEqual(str(teac["status"]), "no_evidence_chain")
        self.assertEqual(str(teac["next_action"]), "backfill_evidence_date_quote_for_official_review_metrics")

    def test_report_queue_highlights_partial_kpi_coverage(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "status_partial_kpi.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)

                data_seed_path = Path(__file__).resolve().parents[1] / "etl" / "data" / "seeds" / "sanction_data_catalog_seed_v1.json"
                data_seed_doc = json.loads(data_seed_path.read_text(encoding="utf-8"))
                import_catalog_seed(conn, seed_doc=data_seed_doc, source_id="", snapshot_date="2026-02-24")
                self._insert_source(conn)

                pk_rate = self._insert_source_record(conn, "teac:2025:rate")
                pk_formal = self._insert_source_record(conn, "teac:2025:formal")
                self._insert_metric(
                    conn,
                    metric_key="kpi:recurso_estimation_rate|es:sanctions:teac_resolutions|2025-12-31|year",
                    kpi_id="kpi:recurso_estimation_rate",
                    sanction_source_id="es:sanctions:teac_resolutions",
                    period_date="2025-12-31",
                    source_record_pk=pk_rate,
                )
                self._insert_metric(
                    conn,
                    metric_key="kpi:formal_annulment_rate|es:sanctions:teac_resolutions|2025-12-31|year",
                    kpi_id="kpi:formal_annulment_rate",
                    sanction_source_id="es:sanctions:teac_resolutions",
                    period_date="2025-12-31",
                    source_record_pk=pk_formal,
                )

                got = build_status_report(conn, period_date="2025-12-31", period_granularity="year")
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "degraded")
        self.assertEqual(str(got["metric_scope"]["label"]), "period")
        self.assertEqual(str(got["metric_scope"]["period_date"]), "2025-12-31")
        self.assertEqual(int(got["totals"]["official_review_kpis_expected_total"]), 3)
        self.assertEqual(int(got["totals"]["official_review_sources_with_metrics_total"]), 1)
        self.assertEqual(int(got["totals"]["official_review_sources_with_all_kpis_total"]), 0)

        queue_by_source = {str(row["sanction_source_id"]): row for row in got["queue"]}
        teac = queue_by_source["es:sanctions:teac_resolutions"]
        self.assertEqual(str(teac["status"]), "partial_kpi_coverage")
        self.assertEqual(int(teac["kpis_expected_total"]), 3)
        self.assertEqual(int(teac["kpis_covered_total"]), 2)
        self.assertEqual(int(teac["kpis_missing_total"]), 1)
        self.assertEqual(str(teac["next_action"]), "ingest_missing_kpis_for_source_scope")

    def test_report_period_scope_ignores_other_period_rows(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "status_period_scope.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)

                data_seed_path = Path(__file__).resolve().parents[1] / "etl" / "data" / "seeds" / "sanction_data_catalog_seed_v1.json"
                data_seed_doc = json.loads(data_seed_path.read_text(encoding="utf-8"))
                import_catalog_seed(conn, seed_doc=data_seed_doc, source_id="", snapshot_date="2026-02-24")
                self._insert_source(conn)

                pk1 = self._insert_source_record(conn, "teac:2024:rate")
                pk2 = self._insert_source_record(conn, "teac:2024:formal")
                pk3 = self._insert_source_record(conn, "teac:2024:p90")
                self._insert_metric(
                    conn,
                    metric_key="kpi:recurso_estimation_rate|es:sanctions:teac_resolutions|2024-12-31|year",
                    kpi_id="kpi:recurso_estimation_rate",
                    sanction_source_id="es:sanctions:teac_resolutions",
                    period_date="2024-12-31",
                    source_record_pk=pk1,
                )
                self._insert_metric(
                    conn,
                    metric_key="kpi:formal_annulment_rate|es:sanctions:teac_resolutions|2024-12-31|year",
                    kpi_id="kpi:formal_annulment_rate",
                    sanction_source_id="es:sanctions:teac_resolutions",
                    period_date="2024-12-31",
                    source_record_pk=pk2,
                )
                self._insert_metric(
                    conn,
                    metric_key="kpi:resolution_delay_p90_days|es:sanctions:teac_resolutions|2024-12-31|year",
                    kpi_id="kpi:resolution_delay_p90_days",
                    sanction_source_id="es:sanctions:teac_resolutions",
                    period_date="2024-12-31",
                    source_record_pk=pk3,
                )

                got = build_status_report(conn, period_date="2025-12-31", period_granularity="year")
            finally:
                conn.close()

        queue_by_source = {str(row["sanction_source_id"]): row for row in got["queue"]}
        teac = queue_by_source["es:sanctions:teac_resolutions"]
        self.assertEqual(str(teac["status"]), "no_metrics")
        self.assertEqual(int(teac["procedural_metric_rows_total"]), 0)


if __name__ == "__main__":
    unittest.main()
