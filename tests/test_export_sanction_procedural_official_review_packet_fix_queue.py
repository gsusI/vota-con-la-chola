from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from etl.parlamentario_es.db import apply_schema, open_db
from scripts.export_sanction_procedural_official_review_packet_fix_queue import (
    build_packet_fix_queue_report,
)
from scripts.export_sanction_procedural_official_review_raw_packets_from_kpi_gap_queue import (
    build_raw_packets_from_gap_queue,
)
from scripts.export_sanction_procedural_official_review_raw_template import RAW_FIELDNAMES
from scripts.import_sanction_data_catalog_seed import import_seed as import_catalog_seed


class TestExportSanctionProceduralOfficialReviewPacketFixQueue(unittest.TestCase):
    def _seed_catalog(self, conn: object) -> None:
        seed_path = (
            Path(__file__).resolve().parents[1]
            / "etl"
            / "data"
            / "seeds"
            / "sanction_data_catalog_seed_v1.json"
        )
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

    def _setup_db(self, db_path: Path) -> None:
        conn = open_db(db_path)
        try:
            schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
            apply_schema(conn, schema_path)
            self._seed_catalog(conn)
            self._insert_source(conn)
        finally:
            conn.close()

    def _load_packets(self, db_path: Path) -> list[dict[str, object]]:
        conn = open_db(db_path)
        try:
            got = build_raw_packets_from_gap_queue(
                conn,
                period_date="2025-12-31",
                period_granularity="year",
                statuses={"missing_metric"},
                default_source_id="boe_api_legal",
            )
            return list(got["packets"])
        finally:
            conn.close()

    def _write_packet(self, path: Path, row: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(RAW_FIELDNAMES))
            writer.writeheader()
            writer.writerow({key: row.get(key, "") for key in RAW_FIELDNAMES})

    def test_fix_queue_lists_missing_packet_files(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "packet_fix_missing.db"
            packets_dir = Path(td) / "packets"
            packets_dir.mkdir(parents=True, exist_ok=True)
            self._setup_db(db_path)

            conn = open_db(db_path)
            try:
                report = build_packet_fix_queue_report(
                    conn,
                    packets_dir=packets_dir,
                    period_date="2025-12-31",
                    period_granularity="year",
                    statuses={"missing_metric"},
                )
            finally:
                conn.close()

        self.assertEqual(str(report["status"]), "degraded")
        self.assertEqual(int(report["totals"]["queue_rows_total"]), 4)
        self.assertEqual(int(report["totals"]["queue_rows_by_packet_status"]["missing_packet_file"]), 4)
        first = list(report["queue_preview"])[0]
        self.assertEqual(str(first["packet_status"]), "missing_packet_file")
        self.assertEqual(int(first["priority"]), 100)

    def test_fix_queue_lists_invalid_rows_for_template_packets(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "packet_fix_invalid.db"
            packets_dir = Path(td) / "packets"
            self._setup_db(db_path)
            packets = self._load_packets(db_path)
            for packet in packets:
                self._write_packet(packets_dir / str(packet["packet_filename"]), dict(packet["row"]))

            conn = open_db(db_path)
            try:
                report = build_packet_fix_queue_report(
                    conn,
                    packets_dir=packets_dir,
                    period_date="2025-12-31",
                    period_granularity="year",
                    statuses={"missing_metric"},
                )
            finally:
                conn.close()

        self.assertEqual(str(report["status"]), "degraded")
        self.assertEqual(int(report["totals"]["queue_rows_total"]), 4)
        self.assertEqual(int(report["totals"]["queue_rows_by_packet_status"]["invalid_row"]), 4)
        first = list(report["queue_preview"])[0]
        self.assertEqual(str(first["packet_status"]), "invalid_row")
        self.assertIn("complete_evidence_and_raw_count_fields_then_recheck", str(first["next_action"]))

    def test_fix_queue_excludes_ready_packets(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "packet_fix_mixed.db"
            packets_dir = Path(td) / "packets"
            self._setup_db(db_path)
            packets = self._load_packets(db_path)

            for idx, packet in enumerate(packets):
                row = dict(packet["row"])
                if idx == 0:
                    row["evidence_date"] = "2025-12-31"
                    row["evidence_quote"] = (
                        "Memoria oficial 2025 consolidada para cierre de KPIs procedimentales por fuente."
                    )
                    row["recurso_presentado_count"] = "1000"
                    row["recurso_estimado_count"] = "250"
                    row["anulaciones_formales_count"] = "50"
                    row["resolution_delay_p90_days"] = "120"
                self._write_packet(packets_dir / str(packet["packet_filename"]), row)

            conn = open_db(db_path)
            try:
                report = build_packet_fix_queue_report(
                    conn,
                    packets_dir=packets_dir,
                    period_date="2025-12-31",
                    period_granularity="year",
                    statuses={"missing_metric"},
                )
            finally:
                conn.close()

        self.assertEqual(int(report["totals"]["packets_expected_total"]), 4)
        self.assertEqual(int(report["totals"]["packets_ready_total"]), 1)
        self.assertEqual(int(report["totals"]["queue_rows_total"]), 3)


if __name__ == "__main__":
    unittest.main()
