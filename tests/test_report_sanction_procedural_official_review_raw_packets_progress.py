from __future__ import annotations

import csv
import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

from etl.parlamentario_es.db import apply_schema, open_db
from scripts.export_sanction_procedural_official_review_raw_packets_from_kpi_gap_queue import (
    build_raw_packets_from_gap_queue,
)
from scripts.export_sanction_procedural_official_review_raw_template import RAW_FIELDNAMES
from scripts.import_sanction_data_catalog_seed import import_seed as import_catalog_seed
from scripts.report_sanction_procedural_official_review_raw_packets_progress import (
    build_raw_packets_progress_report,
    main as packets_progress_main,
)


class TestReportSanctionProceduralOfficialReviewRawPacketsProgress(unittest.TestCase):
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
            payload = build_raw_packets_from_gap_queue(
                conn,
                period_date="2025-12-31",
                period_granularity="year",
                statuses={"missing_metric"},
                default_source_id="boe_api_legal",
            )
            return list(payload["packets"])
        finally:
            conn.close()

    def _write_packet_rows(self, path: Path, rows: list[dict[str, object]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(RAW_FIELDNAMES))
            writer.writeheader()
            for row in rows:
                writer.writerow({key: row.get(key, "") for key in RAW_FIELDNAMES})

    def _run_main(self, argv: list[str]) -> int:
        import sys

        old = sys.argv[:]
        try:
            sys.argv = argv
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                return int(packets_progress_main())
        finally:
            sys.argv = old

    def test_report_detects_missing_packet_files(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "packets_progress_missing.db"
            packets_dir = Path(td) / "packets"
            packets_dir.mkdir(parents=True, exist_ok=True)
            self._setup_db(db_path)
            conn = open_db(db_path)
            try:
                report = build_raw_packets_progress_report(
                    conn,
                    packets_dir=packets_dir,
                    period_date="2025-12-31",
                    period_granularity="year",
                    statuses={"missing_metric"},
                )
            finally:
                conn.close()

        self.assertEqual(str(report["status"]), "degraded")
        self.assertEqual(int(report["totals"]["packets_expected_total"]), 4)
        self.assertEqual(int(report["totals"]["packets_missing_total"]), 4)
        self.assertEqual(int(report["totals"]["packets_ready_total"]), 0)
        self.assertEqual(int(report["totals"]["packets_status_counts"]["missing_packet_file"]), 4)

    def test_report_ready_when_all_packet_rows_valid(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "packets_progress_ready.db"
            packets_dir = Path(td) / "packets"
            self._setup_db(db_path)
            packets = self._load_packets(db_path)

            for packet in packets:
                row = dict(packet["row"])
                row["evidence_date"] = "2025-12-31"
                row["evidence_quote"] = (
                    "Memoria oficial 2025 consolidada para cierre de KPIs procedimentales por fuente."
                )
                row["recurso_presentado_count"] = "1000"
                row["recurso_estimado_count"] = "250"
                row["anulaciones_formales_count"] = "50"
                row["resolution_delay_p90_days"] = "120"
                self._write_packet_rows(packets_dir / str(packet["packet_filename"]), [row])

            conn = open_db(db_path)
            try:
                report = build_raw_packets_progress_report(
                    conn,
                    packets_dir=packets_dir,
                    period_date="2025-12-31",
                    period_granularity="year",
                    statuses={"missing_metric"},
                )
            finally:
                conn.close()

        self.assertEqual(str(report["status"]), "ok")
        self.assertEqual(int(report["totals"]["packets_expected_total"]), 4)
        self.assertEqual(int(report["totals"]["packets_ready_total"]), 4)
        self.assertEqual(int(report["totals"]["packets_not_ready_total"]), 0)
        self.assertTrue(bool(report["checks"]["all_expected_packets_ready"]))

    def test_main_strict_ready_fails_when_any_packet_invalid(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "packets_progress_strict.db"
            packets_dir = Path(td) / "packets"
            out_path = Path(td) / "out.json"
            csv_path = Path(td) / "out.csv"
            self._setup_db(db_path)
            packets = self._load_packets(db_path)

            for idx, packet in enumerate(packets):
                row = dict(packet["row"])
                row["evidence_date"] = "2025-12-31"
                row["evidence_quote"] = (
                    "Memoria oficial 2025 consolidada para cierre de KPIs procedimentales por fuente."
                )
                row["recurso_presentado_count"] = "1000"
                row["recurso_estimado_count"] = "250"
                row["anulaciones_formales_count"] = "50"
                row["resolution_delay_p90_days"] = "120"
                if idx == 0:
                    row["evidence_quote"] = "cita corta"
                self._write_packet_rows(packets_dir / str(packet["packet_filename"]), [row])

            rc = self._run_main(
                [
                    "report_sanction_procedural_official_review_raw_packets_progress.py",
                    "--db",
                    str(db_path),
                    "--packets-dir",
                    str(packets_dir),
                    "--period-date",
                    "2025-12-31",
                    "--period-granularity",
                    "year",
                    "--statuses",
                    "missing_metric",
                    "--strict-ready",
                    "--csv-out",
                    str(csv_path),
                    "--out",
                    str(out_path),
                ]
            )
            payload = json.loads(out_path.read_text(encoding="utf-8"))

        self.assertEqual(rc, 4)
        self.assertEqual(str(payload["status"]), "degraded")
        self.assertEqual(int(payload["totals"]["packets_expected_total"]), 4)
        self.assertEqual(int(payload["totals"]["packets_ready_total"]), 3)
        self.assertEqual(int(payload["totals"]["packets_status_counts"]["invalid_row"]), 1)


if __name__ == "__main__":
    unittest.main()
