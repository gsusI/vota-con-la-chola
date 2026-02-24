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
from scripts.run_sanction_procedural_official_review_packet_fix_ready_cycle import (
    main as packet_fix_ready_cycle_main,
)


class TestRunSanctionProceduralOfficialReviewPacketFixReadyCycle(unittest.TestCase):
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

    def _run_main(self, argv: list[str]) -> int:
        import sys

        old = sys.argv[:]
        try:
            sys.argv = argv
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                return int(packet_fix_ready_cycle_main())
        finally:
            sys.argv = old

    def test_cycle_reports_fix_queue_and_skips_ready_cycle_when_none_ready(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "packet_fix_ready_none.db"
            packets_dir = Path(td) / "packets"
            out_path = Path(td) / "out.json"
            fix_csv_path = Path(td) / "fix.csv"
            self._setup_db(db_path)
            packets = self._load_packets(db_path)
            for packet in packets:
                self._write_packet(packets_dir / str(packet["packet_filename"]), dict(packet["row"]))

            rc = self._run_main(
                [
                    "run_sanction_procedural_official_review_packet_fix_ready_cycle.py",
                    "--db",
                    str(db_path),
                    "--packets-dir",
                    str(packets_dir),
                    "--period-date",
                    "2025-12-31",
                    "--period-granularity",
                    "year",
                    "--fix-csv-out",
                    str(fix_csv_path),
                    "--out",
                    str(out_path),
                ]
            )
            payload = json.loads(out_path.read_text(encoding="utf-8"))

        self.assertEqual(rc, 0)
        self.assertEqual(int(payload["fix_queue"]["totals"]["queue_rows_total"]), 4)
        self.assertEqual(str(payload["ready_cycle"]["cycle"]["cycle"]["apply"]["skip_reason"]), "no_ready_packets")

    def test_strict_fix_empty_blocks_when_queue_not_empty(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "packet_fix_ready_strict.db"
            packets_dir = Path(td) / "packets"
            out_path = Path(td) / "out.json"
            fix_csv_path = Path(td) / "fix.csv"
            self._setup_db(db_path)
            packets = self._load_packets(db_path)
            for packet in packets:
                self._write_packet(packets_dir / str(packet["packet_filename"]), dict(packet["row"]))

            rc = self._run_main(
                [
                    "run_sanction_procedural_official_review_packet_fix_ready_cycle.py",
                    "--db",
                    str(db_path),
                    "--packets-dir",
                    str(packets_dir),
                    "--period-date",
                    "2025-12-31",
                    "--period-granularity",
                    "year",
                    "--strict-fix-empty",
                    "--fix-csv-out",
                    str(fix_csv_path),
                    "--out",
                    str(out_path),
                ]
            )
            payload = json.loads(out_path.read_text(encoding="utf-8"))

        self.assertEqual(rc, 4)
        self.assertEqual(int(payload["fix_queue"]["totals"]["queue_rows_total"]), 4)
        self.assertEqual(str(payload["ready_cycle"]["cycle"]["apply"]["skip_reason"]), "fix_queue_not_empty")

    def test_cycle_passes_with_fixture_ready_packets(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "packet_fix_ready_fixture.db"
            packets_dir = Path(td) / "packets"
            out_path = Path(td) / "out.json"
            fix_csv_path = Path(td) / "fix.csv"
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
                self._write_packet(packets_dir / str(packet["packet_filename"]), row)

            rc = self._run_main(
                [
                    "run_sanction_procedural_official_review_packet_fix_ready_cycle.py",
                    "--db",
                    str(db_path),
                    "--packets-dir",
                    str(packets_dir),
                    "--period-date",
                    "2025-12-31",
                    "--period-granularity",
                    "year",
                    "--strict-fix-empty",
                    "--strict-min-ready",
                    "--min-ready-packets",
                    "1",
                    "--strict-raw",
                    "--strict-prepare",
                    "--strict-readiness",
                    "--dry-run",
                    "--fix-csv-out",
                    str(fix_csv_path),
                    "--out",
                    str(out_path),
                ]
            )
            payload = json.loads(out_path.read_text(encoding="utf-8"))

        self.assertEqual(rc, 0)
        self.assertEqual(int(payload["fix_queue"]["totals"]["queue_rows_total"]), 0)
        self.assertEqual(int(payload["ready_cycle"]["ready_packets_selected_total"]), 4)
        self.assertEqual(str(payload["ready_cycle"]["cycle"]["raw"]["status"]), "ok")
        self.assertEqual(str(payload["ready_cycle"]["cycle"]["prepare"]["status"]), "ok")
        self.assertEqual(str(payload["ready_cycle"]["cycle"]["cycle"]["readiness"]["status"]), "ok")
        self.assertEqual(int(payload["ready_cycle"]["cycle"]["cycle"]["apply"]["counts"]["rows_ready"]), 12)


if __name__ == "__main__":
    unittest.main()
