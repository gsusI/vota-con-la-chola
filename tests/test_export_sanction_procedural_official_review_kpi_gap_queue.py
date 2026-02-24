from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from etl.parlamentario_es.db import apply_schema, open_db
from scripts.export_sanction_procedural_official_review_kpi_gap_queue import build_kpi_gap_queue_report
from scripts.import_sanction_data_catalog_seed import import_seed as import_catalog_seed
from scripts.report_sanction_procedural_official_review_status import OFFICIAL_REVIEW_SOURCE_IDS


class TestExportSanctionProceduralOfficialReviewKpiGapQueue(unittest.TestCase):
    def _seed_catalog(self, conn: object) -> None:
        seed_path = Path(__file__).resolve().parents[1] / "etl" / "data" / "seeds" / "sanction_data_catalog_seed_v1.json"
        seed_doc = json.loads(seed_path.read_text(encoding="utf-8"))
        import_catalog_seed(conn, seed_doc=seed_doc, source_id="", snapshot_date="2026-02-24")

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
        source_record_pk: int | None,
        evidence_date: str | None,
        evidence_quote: str | None,
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
                "boe_api_legal" if source_record_pk is not None else None,
                "https://sede.agenciatributaria.gob.es/",
                source_record_pk,
                evidence_date,
                evidence_quote,
                "{}",
                "2026-02-24T00:00:00+00:00",
                "2026-02-24T00:00:00+00:00",
            ),
        )
        conn.commit()

    def test_report_failed_when_sources_and_kpis_are_missing(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "kpi_gap_failed.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                got = build_kpi_gap_queue_report(conn)
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "failed")
        self.assertEqual(int(got["totals"]["official_review_sources_expected_total"]), len(OFFICIAL_REVIEW_SOURCE_IDS))
        self.assertEqual(int(got["totals"]["official_review_sources_seeded_total"]), 0)
        self.assertEqual(int(got["totals"]["official_review_kpis_expected_total"]), 0)
        self.assertEqual(int(got["totals"]["expected_pairs_total"]), 0)
        self.assertEqual(int(got["totals"]["queue_rows_total"]), 0)
        self.assertFalse(bool(got["checks"]["sources_seeded"]))
        self.assertFalse(bool(got["checks"]["kpis_defined"]))

    def test_report_degraded_with_pair_level_statuses(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "kpi_gap_pairs.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                self._seed_catalog(conn)
                self._insert_source(conn)

                src = "es:sanctions:teac_resolutions"
                period_date = "2025-12-31"

                pk_ready = self._insert_source_record(conn, "teac:2025:recurso_estimation_rate")
                self._insert_metric(
                    conn,
                    metric_key=f"kpi:recurso_estimation_rate|{src}|{period_date}|year",
                    kpi_id="kpi:recurso_estimation_rate",
                    sanction_source_id=src,
                    period_date=period_date,
                    source_record_pk=pk_ready,
                    evidence_date=period_date,
                    evidence_quote="Memoria oficial TEAC 2025 para tasa de estimacion.",
                )
                self._insert_metric(
                    conn,
                    metric_key=f"kpi:formal_annulment_rate|{src}|{period_date}|year",
                    kpi_id="kpi:formal_annulment_rate",
                    sanction_source_id=src,
                    period_date=period_date,
                    source_record_pk=None,
                    evidence_date=period_date,
                    evidence_quote="Memoria oficial TEAC 2025 para anulaciones formales.",
                )
                pk_evidence_gap = self._insert_source_record(conn, "teac:2025:resolution_delay_p90_days")
                self._insert_metric(
                    conn,
                    metric_key=f"kpi:resolution_delay_p90_days|{src}|{period_date}|year",
                    kpi_id="kpi:resolution_delay_p90_days",
                    sanction_source_id=src,
                    period_date=period_date,
                    source_record_pk=pk_evidence_gap,
                    evidence_date=None,
                    evidence_quote=None,
                )

                got = build_kpi_gap_queue_report(conn, period_date=period_date, period_granularity="year")
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "degraded")
        self.assertEqual(int(got["totals"]["expected_pairs_total"]), 12)
        self.assertEqual(int(got["totals"]["pairs_ready_total"]), 1)
        self.assertEqual(int(got["totals"]["pairs_missing_metric_total"]), 9)
        self.assertEqual(int(got["totals"]["pairs_missing_source_record_total"]), 1)
        self.assertEqual(int(got["totals"]["pairs_missing_evidence_total"]), 1)
        self.assertEqual(int(got["totals"]["actionable_pairs_total"]), 11)
        self.assertEqual(int(got["totals"]["queue_rows_total"]), 11)

        teac_rows = [
            row for row in got["queue_rows"] if str(row["sanction_source_id"]) == "es:sanctions:teac_resolutions"
        ]
        by_kpi = {str(row["kpi_id"]): row for row in teac_rows}
        self.assertNotIn("kpi:recurso_estimation_rate", by_kpi)
        self.assertEqual(str(by_kpi["kpi:formal_annulment_rate"]["status"]), "missing_source_record")
        self.assertEqual(
            str(by_kpi["kpi:formal_annulment_rate"]["next_action"]),
            "backfill_source_record_pk_for_official_review_metric",
        )
        self.assertEqual(str(by_kpi["kpi:resolution_delay_p90_days"]["status"]), "missing_evidence")
        self.assertEqual(
            str(by_kpi["kpi:resolution_delay_p90_days"]["next_action"]),
            "backfill_evidence_date_quote_for_official_review_metric",
        )

    def test_report_period_scope_ignores_other_period_rows(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "kpi_gap_period_scope.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                self._seed_catalog(conn)
                self._insert_source(conn)

                src = "es:sanctions:teac_resolutions"
                period_2024 = "2024-12-31"
                for kpi_id in (
                    "kpi:recurso_estimation_rate",
                    "kpi:formal_annulment_rate",
                    "kpi:resolution_delay_p90_days",
                ):
                    pk = self._insert_source_record(conn, f"teac:2024:{kpi_id}")
                    self._insert_metric(
                        conn,
                        metric_key=f"{kpi_id}|{src}|{period_2024}|year",
                        kpi_id=kpi_id,
                        sanction_source_id=src,
                        period_date=period_2024,
                        source_record_pk=pk,
                        evidence_date=period_2024,
                        evidence_quote="Evidencia oficial TEAC 2024.",
                    )

                got = build_kpi_gap_queue_report(conn, period_date="2025-12-31", period_granularity="year")
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "degraded")
        self.assertEqual(str(got["metric_scope"]["label"]), "period")
        self.assertEqual(str(got["metric_scope"]["period_date"]), "2025-12-31")
        self.assertEqual(int(got["totals"]["pairs_ready_total"]), 0)
        self.assertEqual(int(got["totals"]["pairs_missing_metric_total"]), 12)
        self.assertEqual(int(got["totals"]["queue_rows_total"]), 12)

        teac_rows = [
            row for row in got["queue_rows"] if str(row["sanction_source_id"]) == "es:sanctions:teac_resolutions"
        ]
        self.assertEqual(len(teac_rows), 3)
        self.assertTrue(all(str(row["status"]) == "missing_metric" for row in teac_rows))


if __name__ == "__main__":
    unittest.main()
