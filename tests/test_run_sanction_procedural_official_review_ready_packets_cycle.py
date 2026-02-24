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
from scripts.run_sanction_procedural_official_review_ready_packets_cycle import (
    main as ready_packets_cycle_main,
)


class TestRunSanctionProceduralOfficialReviewReadyPacketsCycle(unittest.TestCase):
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

    def _run_cycle(self, argv: list[str]) -> int:
        import sys

        old = sys.argv[:]
        try:
            sys.argv = argv
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                return int(ready_packets_cycle_main())
        finally:
            sys.argv = old

    def test_skip_when_no_ready_packets(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "ready_packets_none.db"
            packets_dir = Path(td) / "packets"
            out_path = Path(td) / "out.json"
            self._setup_db(db_path)
            packets = self._load_packets(db_path)
            for packet in packets:
                row = dict(packet["row"])
                self._write_packet(packets_dir / str(packet["packet_filename"]), row)

            rc = self._run_cycle(
                [
                    "run_sanction_procedural_official_review_ready_packets_cycle.py",
                    "--db",
                    str(db_path),
                    "--packets-dir",
                    str(packets_dir),
                    "--period-date",
                    "2025-12-31",
                    "--period-granularity",
                    "year",
                    "--out",
                    str(out_path),
                ]
            )
            payload = json.loads(out_path.read_text(encoding="utf-8"))

        self.assertEqual(rc, 0)
        self.assertEqual(int(payload["progress"]["totals"]["packets_expected_total"]), 4)
        self.assertEqual(int(payload["progress"]["totals"]["packets_ready_total"]), 0)
        self.assertEqual(str(payload["cycle"]["cycle"]["apply"]["skip_reason"]), "no_ready_packets")

    def test_strict_min_ready_fails_when_no_ready_packets(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "ready_packets_none_strict.db"
            packets_dir = Path(td) / "packets"
            out_path = Path(td) / "out.json"
            self._setup_db(db_path)
            packets = self._load_packets(db_path)
            for packet in packets:
                row = dict(packet["row"])
                self._write_packet(packets_dir / str(packet["packet_filename"]), row)

            rc = self._run_cycle(
                [
                    "run_sanction_procedural_official_review_ready_packets_cycle.py",
                    "--db",
                    str(db_path),
                    "--packets-dir",
                    str(packets_dir),
                    "--period-date",
                    "2025-12-31",
                    "--period-granularity",
                    "year",
                    "--strict-min-ready",
                    "--out",
                    str(out_path),
                ]
            )
            payload = json.loads(out_path.read_text(encoding="utf-8"))

        self.assertEqual(rc, 4)
        self.assertEqual(str(payload["cycle"]["cycle"]["apply"]["skip_reason"]), "no_ready_packets")

    def test_partial_ready_packets_runs_cycle_with_ready_subset(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "ready_packets_partial.db"
            packets_dir = Path(td) / "packets"
            out_path = Path(td) / "out.json"
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

            rc = self._run_cycle(
                [
                    "run_sanction_procedural_official_review_ready_packets_cycle.py",
                    "--db",
                    str(db_path),
                    "--packets-dir",
                    str(packets_dir),
                    "--period-date",
                    "2025-12-31",
                    "--period-granularity",
                    "year",
                    "--min-ready-packets",
                    "1",
                    "--strict-min-ready",
                    "--strict-raw",
                    "--strict-prepare",
                    "--strict-readiness",
                    "--dry-run",
                    "--out",
                    str(out_path),
                ]
            )
            payload = json.loads(out_path.read_text(encoding="utf-8"))
            conn = open_db(db_path)
            try:
                n = int(conn.execute("SELECT COUNT(*) AS n FROM sanction_procedural_metrics").fetchone()["n"])
            finally:
                conn.close()

        self.assertEqual(rc, 0)
        self.assertEqual(int(payload["progress"]["totals"]["packets_ready_total"]), 1)
        self.assertEqual(int(payload["ready_packets_selected_total"]), 1)
        self.assertEqual(str(payload["cycle"]["raw"]["status"]), "ok")
        self.assertEqual(int(payload["cycle"]["raw"]["totals"]["kpi_rows_emitted"]), 3)
        self.assertEqual(str(payload["cycle"]["prepare"]["status"]), "ok")
        self.assertEqual(str(payload["cycle"]["cycle"]["readiness"]["status"]), "ok")
        self.assertEqual(int(payload["cycle"]["cycle"]["apply"]["counts"]["rows_ready"]), 3)
        self.assertEqual(n, 0)


if __name__ == "__main__":
    unittest.main()
