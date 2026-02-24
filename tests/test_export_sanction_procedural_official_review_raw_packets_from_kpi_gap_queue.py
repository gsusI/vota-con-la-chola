from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from etl.parlamentario_es.db import apply_schema, open_db
from scripts.export_sanction_procedural_official_review_raw_packets_from_kpi_gap_queue import (
    build_raw_packets_from_gap_queue,
)
from scripts.import_sanction_data_catalog_seed import import_seed as import_catalog_seed


class TestExportSanctionProceduralOfficialReviewRawPacketsFromKpiGapQueue(unittest.TestCase):
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

    def _insert_metric_missing_source_record(self, conn: object) -> None:
        conn.execute(
            """
            INSERT INTO sanction_procedural_metrics (
              metric_key, kpi_id, sanction_source_id, period_date, period_granularity,
              value, numerator, denominator, source_id, source_url, source_record_pk,
              evidence_date, evidence_quote, raw_payload, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "kpi:formal_annulment_rate|es:sanctions:teac_resolutions|2025-12-31|year",
                "kpi:formal_annulment_rate",
                "es:sanctions:teac_resolutions",
                "2025-12-31",
                "year",
                0.05,
                5.0,
                100.0,
                None,
                "https://sede.agenciatributaria.gob.es/",
                None,
                "2025-12-31",
                "Memoria oficial TEAC 2025 con datos de anulaciones formales.",
                "{}",
                "2026-02-24T00:00:00+00:00",
                "2026-02-24T00:00:00+00:00",
            ),
        )
        conn.commit()

    def test_report_failed_when_gap_queue_failed(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "raw_packets_failed.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                got = build_raw_packets_from_gap_queue(
                    conn,
                    period_date="2025-12-31",
                    period_granularity="year",
                    statuses={"missing_metric"},
                )
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "failed")
        self.assertEqual(int(got["totals"]["sources_actionable_total"]), 0)
        self.assertFalse(bool(got["checks"]["gap_queue_not_failed"]))

    def test_report_emits_one_packet_per_source_for_missing_metric_backlog(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "raw_packets_missing_metric.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                self._seed_catalog(conn)
                got = build_raw_packets_from_gap_queue(
                    conn,
                    period_date="2025-12-31",
                    period_granularity="year",
                    statuses={"missing_metric"},
                    default_source_id="boe_api_legal",
                )
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "ok")
        self.assertEqual(int(got["totals"]["sources_actionable_total"]), 4)
        self.assertEqual(int(got["totals"]["packets_emitted_total"]), 4)
        self.assertEqual(int(got["totals"]["rows_skipped_filtered_status_total"]), 0)

        packet = list(got["packets"])[0]
        row = dict(packet["row"])
        self.assertIn("es:sanctions:", str(packet["sanction_source_id"]))
        self.assertEqual(str(row["period_date"]), "2025-12-31")
        self.assertEqual(str(row["period_granularity"]), "year")
        self.assertEqual(str(row["source_id"]), "boe_api_legal")
        self.assertIn("official_review_raw:", str(row["source_record_id"]))

    def test_report_filters_statuses_and_builds_single_packet(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "raw_packets_filter_status.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                self._seed_catalog(conn)
                self._insert_source(conn)
                self._insert_metric_missing_source_record(conn)

                got = build_raw_packets_from_gap_queue(
                    conn,
                    period_date="2025-12-31",
                    period_granularity="year",
                    statuses={"missing_source_record"},
                    default_source_id="boe_api_legal",
                )
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "ok")
        self.assertEqual(int(got["totals"]["sources_actionable_total"]), 1)
        self.assertEqual(int(got["totals"]["packets_emitted_total"]), 1)
        self.assertEqual(int(got["totals"]["rows_skipped_filtered_status_total"]), 11)
        packet = list(got["packets"])[0]
        self.assertEqual(str(packet["sanction_source_id"]), "es:sanctions:teac_resolutions")
        self.assertEqual(int(packet["kpis_missing_total"]), 1)
        self.assertEqual(list(packet["kpis_missing"]), ["kpi:formal_annulment_rate"])


if __name__ == "__main__":
    unittest.main()
