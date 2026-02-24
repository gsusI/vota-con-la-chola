from __future__ import annotations

import csv
import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

from etl.parlamentario_es.db import apply_schema, open_db
from scripts.import_sanction_data_catalog_seed import import_seed as import_catalog_seed
from scripts.run_sanction_procedural_official_review_apply_cycle import main as cycle_main


class TestRunSanctionProceduralOfficialReviewApplyCycle(unittest.TestCase):
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

    def _setup_db(self, db_path: Path) -> None:
        conn = open_db(db_path)
        try:
            schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
            apply_schema(conn, schema_path)
            self._insert_source(conn)
            self._seed_catalog(conn)
        finally:
            conn.close()

    def _run_cycle(self, argv: list[str]) -> int:
        import sys

        old = sys.argv[:]
        try:
            sys.argv = argv
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                return int(cycle_main())
        finally:
            sys.argv = old

    def test_cycle_strict_readiness_blocks_apply(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "cycle_block.db"
            csv_path = Path(td) / "bad.csv"
            out_path = Path(td) / "out.json"
            self._setup_db(db_path)

            with csv_path.open("w", encoding="utf-8", newline="") as fh:
                writer = csv.DictWriter(
                    fh,
                    fieldnames=[
                        "sanction_source_id",
                        "kpi_id",
                        "period_date",
                        "period_granularity",
                        "value",
                        "numerator",
                        "denominator",
                        "source_url",
                        "evidence_date",
                        "evidence_quote",
                        "source_id",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "sanction_source_id": "es:sanctions:teac_resolutions",
                        "kpi_id": "kpi:recurso_estimation_rate",
                        "period_date": "2025-12-31",
                        "period_granularity": "year",
                        "value": "",
                        "numerator": "20",
                        "denominator": "100",
                        "source_url": "https://example.org/teac/2025",
                        "evidence_date": "2025-12-31",
                        "evidence_quote": "Memoria oficial TEAC 2025, apartado de recursos estimados.",
                        "source_id": "boe_api_legal",
                    }
                )

            rc = self._run_cycle(
                [
                    "run_sanction_procedural_official_review_apply_cycle.py",
                    "--db",
                    str(db_path),
                    "--in",
                    str(csv_path),
                    "--strict-readiness",
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

        self.assertEqual(rc, 4)
        self.assertEqual(str(payload["readiness"]["status"]), "degraded")
        self.assertTrue(bool(payload["apply"]["skipped"]))
        self.assertEqual(str(payload["apply"]["skip_reason"]), "readiness_not_ok")
        self.assertEqual(n, 0)

    def test_cycle_applies_rows_when_ready(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "cycle_ok.db"
            csv_path = Path(td) / "ok.csv"
            out_path = Path(td) / "out.json"
            self._setup_db(db_path)

            with csv_path.open("w", encoding="utf-8", newline="") as fh:
                writer = csv.DictWriter(
                    fh,
                    fieldnames=[
                        "sanction_source_id",
                        "kpi_id",
                        "period_date",
                        "period_granularity",
                        "value",
                        "numerator",
                        "denominator",
                        "source_url",
                        "evidence_date",
                        "evidence_quote",
                        "source_id",
                        "source_record_id",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "sanction_source_id": "es:sanctions:teac_resolutions",
                        "kpi_id": "kpi:recurso_estimation_rate",
                        "period_date": "2025-12-31",
                        "period_granularity": "year",
                        "value": "0.2",
                        "numerator": "20",
                        "denominator": "100",
                        "source_url": "https://example.org/teac/2025",
                        "evidence_date": "2025-12-31",
                        "evidence_quote": "Memoria oficial TEAC 2025, tabla anual consolidada de recursos.",
                        "source_id": "boe_api_legal",
                        "source_record_id": "teac:2025:recurso_estimation_rate",
                    }
                )

            rc = self._run_cycle(
                [
                    "run_sanction_procedural_official_review_apply_cycle.py",
                    "--db",
                    str(db_path),
                    "--in",
                    str(csv_path),
                    "--strict-readiness",
                    "--snapshot-date",
                    "2026-02-24",
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
        self.assertEqual(str(payload["readiness"]["status"]), "ok")
        self.assertFalse(bool(payload["apply"]["skipped"]))
        self.assertEqual(int(payload["apply"]["counts"]["rows_upserted"]), 1)
        self.assertEqual(n, 1)


if __name__ == "__main__":
    unittest.main()
