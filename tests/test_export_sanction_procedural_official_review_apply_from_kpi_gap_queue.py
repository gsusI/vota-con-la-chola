from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from etl.parlamentario_es.db import apply_schema, open_db
from scripts.export_sanction_procedural_official_review_apply_from_kpi_gap_queue import (
    build_apply_rows_from_gap_queue,
)
from scripts.import_sanction_data_catalog_seed import import_seed as import_catalog_seed


class TestExportSanctionProceduralOfficialReviewApplyFromKpiGapQueue(unittest.TestCase):
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
                0.2 if kpi_id != "kpi:resolution_delay_p90_days" else 120.0,
                20.0 if kpi_id != "kpi:resolution_delay_p90_days" else None,
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

    def test_build_apply_rows_failed_when_gap_queue_failed(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "apply_gap_failed.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                got = build_apply_rows_from_gap_queue(conn)
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "failed")
        self.assertEqual(int(got["totals"]["queue_rows_seen_total"]), 0)
        self.assertEqual(int(got["totals"]["rows_emitted_total"]), 0)

    def test_build_apply_rows_emits_missing_metric_rows(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "apply_gap_missing_metric.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                self._seed_catalog(conn)

                got = build_apply_rows_from_gap_queue(
                    conn,
                    period_date="2025-12-31",
                    period_granularity="year",
                    default_source_id="boe_api_legal",
                )
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "ok")
        self.assertEqual(int(got["totals"]["queue_rows_seen_total"]), 12)
        self.assertEqual(int(got["totals"]["rows_emitted_total"]), 12)
        self.assertEqual(int(got["totals"]["rows_emitted_by_status"]["missing_metric"]), 12)

        row = list(got["rows_preview"])[0]
        self.assertEqual(str(row["queue_status"]), "missing_metric")
        self.assertEqual(str(row["value"]), "")
        self.assertEqual(str(row["source_id"]), "boe_api_legal")
        self.assertIn("kpi:", str(row["metric_key"]))

    def test_build_apply_rows_prefills_chain_gap_rows_and_filters_statuses(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "apply_gap_chain_rows.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                self._seed_catalog(conn)
                self._insert_source(conn)

                src = "es:sanctions:teac_resolutions"
                period_date = "2025-12-31"
                pk_ready = self._insert_source_record(conn, "teac:2025:rate")
                pk_p90 = self._insert_source_record(conn, "teac:2025:p90")

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
                self._insert_metric(
                    conn,
                    metric_key=f"kpi:resolution_delay_p90_days|{src}|{period_date}|year",
                    kpi_id="kpi:resolution_delay_p90_days",
                    sanction_source_id=src,
                    period_date=period_date,
                    source_record_pk=pk_p90,
                    evidence_date=None,
                    evidence_quote=None,
                )

                got_all = build_apply_rows_from_gap_queue(
                    conn,
                    period_date=period_date,
                    period_granularity="year",
                    default_source_id="boe_api_legal",
                )
                got_evidence_only = build_apply_rows_from_gap_queue(
                    conn,
                    period_date=period_date,
                    period_granularity="year",
                    default_source_id="boe_api_legal",
                    statuses={"missing_evidence"},
                )
            finally:
                conn.close()

        self.assertEqual(str(got_all["status"]), "ok")
        self.assertEqual(int(got_all["totals"]["rows_emitted_total"]), 11)
        self.assertEqual(int(got_all["totals"]["rows_emitted_by_status"]["missing_metric"]), 9)
        self.assertEqual(int(got_all["totals"]["rows_emitted_by_status"]["missing_source_record"]), 1)
        self.assertEqual(int(got_all["totals"]["rows_emitted_by_status"]["missing_evidence"]), 1)

        all_rows = list(got_all.get("rows", []))
        by_key = {
            str(row["metric_key"]): row
            for row in all_rows
            if str(row["sanction_source_id"]) == "es:sanctions:teac_resolutions"
        }

        formal = by_key[f"kpi:formal_annulment_rate|es:sanctions:teac_resolutions|{period_date}|year"]
        self.assertEqual(str(formal["queue_status"]), "missing_source_record")
        self.assertEqual(str(formal["value"]), "0.2")
        self.assertEqual(str(formal["source_record_pk"]), "")

        p90 = by_key[f"kpi:resolution_delay_p90_days|es:sanctions:teac_resolutions|{period_date}|year"]
        self.assertEqual(str(p90["queue_status"]), "missing_evidence")
        self.assertEqual(str(p90["value"]), "120.0")
        self.assertNotEqual(str(p90["source_record_pk"]), "")
        self.assertEqual(str(p90["source_record_id"]), "teac:2025:p90")
        self.assertEqual(str(p90["evidence_date"]), "")

        self.assertEqual(int(got_evidence_only["totals"]["rows_emitted_total"]), 1)
        only_row = list(got_evidence_only.get("rows", []))[0]
        self.assertEqual(str(only_row["queue_status"]), "missing_evidence")


if __name__ == "__main__":
    unittest.main()
